# MWE prompt-cycle comparison

- Cycle base directory: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1`
- Cycles summarized: 6
- Best F1 cycle: cycle 3 (F1=0.338, precision=0.276, recall=0.434)

## Score trend

| Cycle | Records | Precision | Recall | F1 | Exact | TP | FP | FN | Prompt chars | Prompt lines | Revision chars |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 336 | 0.149 | 0.354 | 0.210 | 0.274 | 62 | 354 | 113 | 1286 | 9 | 1695 |
| 2 | 336 | 0.246 | 0.400 | 0.304 | 0.387 | 70 | 215 | 105 | 1695 | 21 | 1988 |
| 3 **best** | 336 | 0.276 | 0.434 | 0.338 | 0.443 | 76 | 199 | 99 | 1988 | 22 | 2414 |
| 4 | 336 | 0.244 | 0.429 | 0.311 | 0.393 | 75 | 232 | 100 | 2414 | 24 | 2719 |
| 5 | 336 | 0.190 | 0.383 | 0.254 | 0.345 | 67 | 286 | 108 | 2719 | 32 | 3056 |
| 6 | 336 | 0.248 | 0.434 | 0.316 | 0.375 | 76 | 230 | 99 | 3056 | 34 | 3266 |

## Notes for review

- If F1 stalls or declines while prompt size grows, inspect whether later prompts have become too long or overly specific.
- Compare precision/recall changes: falling recall suggests missed MWE classes; falling precision suggests over-broad marking.
- Use this report with each cycle's `prompt_improvement.md` before deciding whether to accept, shorten, or revise the next prompt.

## Artifact paths

### Cycle 1

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_1\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_1\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_1\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_1\improvement\template_revision.txt`

### Cycle 2

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_2\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_2\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_2\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_2\improvement\template_revision.txt`

### Cycle 3

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_3\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_3\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_3\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_3\improvement\template_revision.txt`

### Cycle 4

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_4\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_4\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_4\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_4\improvement\template_revision.txt`

### Cycle 5

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_5\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_5\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_5\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_5\improvement\template_revision.txt`

### Cycle 6

- Summary: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_6\score\summary.md`
- Improvement report: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_6\improvement\prompt_improvement.md`
- Template: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_6\template.txt`
- Next-cycle revision draft: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_analysis_v1\cycle_6\improvement\template_revision.txt`
