"""Named Speech API voices; labels deliberately do not invent gender metadata."""
DEFAULT_VOICE = 'marin'
VOICE_CHOICES = [(name, name.title()) for name in (
    'marin', 'cedar', 'alloy', 'ash', 'ballad', 'coral', 'echo',
    'fable', 'nova', 'onyx', 'sage', 'shimmer', 'verse')]
VOICE_NAMES = {name for name, _ in VOICE_CHOICES}
