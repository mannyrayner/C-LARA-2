"""Local PCM analysis. No recognition, forced alignment or network dependency.

Boundaries are structural candidates, not proof of which words were spoken.
Never delete internal pauses or choose the two largest gaps from many.
"""
from array import array
import io
import math
import sys
import wave
from .tts import normalize_wav, SilentAudio

UserError = ValueError

def wav_check(data):
    try:
        prepared, duration = normalize_wav(data)
    except SilentAudio as exc:
        return data, {"duration": exc.duration, "quiet": True}
    return prepared[0], {"duration": duration, "quiet": False}

ALGORITHM = 'conservative-two-gaps-v2'
DEFAULT = {'threshold_db': -42.0, 'min_pause_ms': 250, 'padding_ms': 120,
           'playback_padding_ms': 200, 'frame_ms': 10,
           'min_prefix_ms': 350, 'min_suffix_ms': 300, 'max_carrier_ms': 3000}


def db(value):
    return round(20 * math.log10(value / 32768), 3) if value else -120.0


def load(data):
    fixed, stats = wav_check(data)
    with wave.open(io.BytesIO(fixed), 'rb') as src:
        rate, channels = src.getframerate(), src.getnchannels()
        pcm = src.readframes(src.getnframes())
    samples = array('h', pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    return {'rate': rate, 'channels': channels, 'pcm': pcm, 'samples': samples,
            'duration': stats['duration'], 'stats': stats}


def encode(pcm, rate, channels):
    out = io.BytesIO()
    with wave.open(out, 'wb') as dst:
        dst.setnchannels(channels); dst.setsampwidth(2); dst.setframerate(rate)
        dst.writeframes(pcm)
    return out.getvalue()


def segment(sound, start, end, pad_ms=0):
    rate, channels = sound['rate'], sound['channels']
    if not 0 <= start < end <= sound['duration'] + 1e-8:
        raise UserError('Invalid audio cut boundaries')
    first, last = round(start * rate), round(end * rate)
    pcm = sound['pcm'][first * channels * 2:last * channels * 2]
    # Identical digital playback pre/post-roll for baseline and carrier extracts.
    silence = bytes(round(rate * pad_ms / 1000) * channels * 2)
    return encode(silence + pcm + silence, rate, channels)


def levels(sound, frame_ms=10):
    count = max(1, round(sound['rate'] * frame_ms / 1000))
    channels, samples = sound['channels'], sound['samples']
    result = []
    for start in range(0, len(samples), count * channels):
        part = samples[start:start + count * channels]
        # Channel maximum avoids cancellation when stereo channels have opposite phase.
        rms = max(math.sqrt(sum(x*x for x in part[c::channels]) / len(part[c::channels]))
                  for c in range(channels))
        result.append({'start': start / channels / sound['rate'],
                       'end': (start + len(part)) / channels / sound['rate'],
                       'rms_dbfs': db(rms), 'peak_dbfs': db(max(abs(x) for x in part))})
    return result


def region_stats(sound, start, end):
    a = round(start * sound['rate']) * sound['channels']
    b = round(end * sound['rate']) * sound['channels']
    samples = sound['samples'][a:b]
    if not samples:
        return {'start': start, 'end': end, 'duration': max(0, end-start),
                'rms_dbfs': -120.0, 'peak_dbfs': -120.0}
    return {'start': round(start, 5), 'end': round(end, 5), 'duration': round(end-start, 5),
            'rms_dbfs': db(math.sqrt(sum(x*x for x in samples)/len(samples))),
            'peak_dbfs': db(max(abs(x) for x in samples))}


def validate_config(config):
    for key, low, high in [('threshold_db', -80, -15), ('min_pause_ms', 100, 1500),
                           ('padding_ms', 20, 250), ('playback_padding_ms', 0, 500),
                           ('min_prefix_ms', 120, 1200), ('min_suffix_ms', 120, 1200),
                           ('max_carrier_ms', 1500, 6000)]:
        value = config[key]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise UserError(f'{key} must be between {low} and {high}')
    if config['frame_ms'] != 10:
        raise UserError('This version uses fixed 10 ms analysis frames')


def measure(sound, config, frames=None):
    validate_config(config)
    frames = frames if frames is not None else levels(sound, config['frame_ms'])
    threshold = config['threshold_db']
    loud = [i for i, f in enumerate(frames) if f['rms_dbfs'] > threshold]
    result = {'status': 'ambiguous', 'reason': '', 'duration': sound['duration'],
              'gaps': [], 'cut': None, 'regions': {}, 'frame_ms': config['frame_ms']}
    if not loud:
        result['reason'] = 'No speech above the selected threshold'
        return result
    first, last = loud[0], loud[-1]
    start = None
    for i in range(first, last + 2):
        quiet = i <= last and frames[i]['rms_dbfs'] <= threshold
        if quiet and start is None:
            start = i
        elif not quiet and start is not None:
            a, b = frames[start]['start'], frames[i-1]['end']
            if (b-a)*1000 + 1e-6 >= config['min_pause_ms']:
                result['gaps'].append(region_stats(sound, a, b))
            start = None
    n = len(result['gaps'])
    if n != 2:
        result['reason'] = f'Expected exactly two internal pauses; found {n}'
        return result
    left, right = result['gaps']
    parts = [(frames[first]['start'], left['start']), (left['end'], right['start']),
             (right['end'], frames[last]['end'])]
    durations = [b-a for a,b in parts]
    result['regions'] = {name: region_stats(sound, x, y)
                         for name, (x, y) in zip(['prefix', 'target', 'suffix'], parts)}
    if min(durations) < .12 or durations[1] > 8:
        result['reason'] = 'Speech sections are implausibly short, or target exceeds 8 seconds'
        return result
    if durations[0] * 1000 < config['min_prefix_ms'] - 1e-6 or durations[2] * 1000 < config['min_suffix_ms'] - 1e-6:
        result['reason'] = 'Carrier section too short: possible cut inside a phrase or missing carrier'
        return result
    if max(durations[0], durations[2]) * 1000 > config['max_carrier_ms'] + 1e-6:
        result['reason'] = 'Carrier section too long: possible missing boundary'
        return result
    # Retain threshold-edge material; cuts stay within their detected quiet intervals.
    pad = config['padding_ms']/1000
    a = left['end'] - min(pad, left['duration']/2)
    b = right['start'] + min(pad, right['duration']/2)
    result.update(status='candidate', reason='Two clear pauses; listener must verify the extracted content',
                  cut={'start': round(a, 5), 'end': round(b, 5)},
                  regions={name: region_stats(sound, x, y)
                           for name,(x,y) in zip(['prefix','target','suffix'],parts)})
    if load(segment(sound, a, b))['stats']['quiet']:
        result.update(status='ambiguous', cut=None, reason='Extracted target is near-silent')
    return result
