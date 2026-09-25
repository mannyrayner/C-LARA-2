# MWE prompt-cycle comparison

- Cycle base directory: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context`
- Cycles summarized: 4
- Best F1 cycle: cycle 2 (F1=0.307, precision=0.261, recall=0.371)

## Score trend

| Cycle | Records | Precision | Recall | F1 | Exact | TP | FP | FN | Prompt chars | Prompt lines | Revision chars |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 336 | 0.221 | 0.331 | 0.265 | 0.399 | 58 | 204 | 117 | 629 | 5 | 1271 |
| 2 **best** | 336 | 0.261 | 0.371 | 0.307 | 0.467 | 65 | 184 | 110 | 1271 | 11 | 1565 |
| 3 | 336 | 0.218 | 0.286 | 0.248 | 0.440 | 50 | 179 | 125 | 1565 | 13 | 1635 |
| 4 | 336 | 0.180 | 0.251 | 0.210 | 0.423 | 44 | 200 | 131 | 1635 | 13 | 1549 |

## Notes for review

- If F1 stalls or declines while prompt size grows, inspect whether later prompts have become too long or overly specific.
- Compare precision/recall changes: falling recall suggests missed MWE classes; falling precision suggests over-broad marking.
- Use this report with each cycle's `prompt_improvement.md` before deciding whether to accept, shorten, or revise the next prompt.

## Artifact paths

### Cycle 1

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_1\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_1\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_1\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_1\improvement\template_revision.txt`

### Cycle 2

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_2\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_2\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_2\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_2\improvement\template_revision.txt`

### Cycle 3

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_3\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_3\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_3\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_3\improvement\template_revision.txt`

### Cycle 4

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_4\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_4\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_4\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context\cycle_4\improvement\template_revision.txt`
