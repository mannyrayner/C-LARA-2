# MWE prompt-cycle comparison

- Cycle base directory: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development`
- Cycles summarized: 5
- Best F1 cycle: cycle 4 (F1=0.374, precision=0.430, recall=0.331)

## Score trend

| Cycle | Records | Precision | Recall | F1 | Exact | TP | FP | FN | Prompt chars | Prompt lines | Revision chars |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 336 | 0.270 | 0.269 | 0.269 | 0.533 | 47 | 127 | 128 | 629 | 5 | 1890 |
| 2 | 336 | 0.358 | 0.280 | 0.314 | 0.577 | 49 | 88 | 126 | 1890 | 23 | 2581 |
| 3 | 336 | 0.313 | 0.297 | 0.305 | 0.506 | 52 | 114 | 123 | 2581 | 29 | 3335 |
| 4 **best** | 336 | 0.430 | 0.331 | 0.374 | 0.568 | 58 | 77 | 117 | 3335 | 33 | 4841 |
| 5 | 336 | 0.329 | 0.269 | 0.296 | 0.533 | 47 | 96 | 128 | 4841 | 45 | 4841 |

## Notes for review

- If F1 stalls or declines while prompt size grows, inspect whether later prompts have become too long or overly specific.
- Compare precision/recall changes: falling recall suggests missed MWE classes; falling precision suggests over-broad marking.
- Use this report with each cycle's `prompt_improvement.md` before deciding whether to accept, shorten, or revise the next prompt.

## Artifact paths

### Cycle 1

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_1\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_1\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_1\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_1\improvement\template_revision.txt`

### Cycle 2

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_2\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_2\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_2\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_2\improvement\template_revision.txt`

### Cycle 3

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_3\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_3\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_3\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_3\improvement\template_revision.txt`

### Cycle 4

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_4\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_4\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_4\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_4\improvement\template_revision.txt`

### Cycle 5

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_5\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_5\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_5\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\cycle_5\improvement\template_revision.txt`
