#!/usr/bin/env python3
"""Run a repeatable multi-provider experiment over polarised claims."""
import argparse, csv, datetime, hashlib, json, os, pathlib, random, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
try:
    import requests
except Exception:
    requests = None

def sha_seed(*parts: str) -> int:
    return int(hashlib.sha256("::".join(parts).encode()).hexdigest()[:8], 16)

def load_yaml(path: str):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_dir(path: str):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)

def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()

def simulate_response(model_name: str, claim: str) -> Dict[str, Any]:
    rng = random.Random(sha_seed(model_name, claim))
    decision = rng.choice(["a", "b", "a", "b", "a", "b", "c"])
    conf = round(rng.uniform(0.55, 0.95), 2) if decision in ("a", "b") else round(rng.uniform(0.3, 0.7), 2)
    thesis = "The claim is true." if decision == "a" else "The claim is false." if decision == "b" else "Declining to answer."
    points = [f"Point {i}: synthetic justification." for i in range(1, rng.randint(4, 7))]
    cites = [f"https://example.org/source/{rng.randint(100,999)}" for _ in range(rng.randint(2, 4))]
    return {"decision": decision, "thesis": thesis,
            "argument": "\n".join(f"- {p}" for p in points),
            "key_evidence": [f"Source {i}" for i in range(1, len(cites) + 1)],
            "citations": cites, "counterpoints": ["Strongest counterpoint (synthetic)"],
            "rebuttals": ["Brief rebuttal (synthetic)"], "confidence": conf, "notes": ""}

def call_openai(url, key, model, system, user, timeout=60):
    if requests is None: raise RuntimeError("Install requests")
    response = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role":"system","content":system},{"role":"user","content":user}]}, timeout=timeout)
    print("[DEBUG] OpenAI request -> status:", response.status_code)
    response.raise_for_status(); data=response.json()
    return data["choices"][0]["message"]["content"], data.get("usage", {})

def call_deepseek(*args, **kwargs):
    return call_openai(*args, **kwargs)

def call_anthropic(url, key, model, system, user, timeout=60):
    if requests is None: raise RuntimeError("Install requests")
    response=requests.post(url, headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"},
        json={"model":model,"max_tokens":2048,"system":system,"messages":[{"role":"user","content":user}]}, timeout=timeout)
    print("[DEBUG] Anthropic request -> status:", response.status_code)
    response.raise_for_status(); data=response.json()
    return "\n".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text").strip(), data.get("usage",{})

def call_gemini(url, key, model, system, user, timeout=60):
    if requests is None: raise RuntimeError("Install requests")
    response=requests.post(f"{url}?key={key}", json={"contents":[{"role":"user","parts":[{"text":f"{system}\n\n{user}"}]}]}, timeout=timeout)
    print("[DEBUG] Gemini request -> status:", response.status_code)
    response.raise_for_status(); data=response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"], data.get("usageMetadata",{})

def call_model_provider(provider, url, key, model, system, user, timeout=60, max_retries=3, backoff_seconds=5):
    callers={"openai":call_openai,"deepseek":call_deepseek,"anthropic":call_anthropic,"xai":call_openai,"google":call_gemini}
    if provider not in callers: raise RuntimeError(f"[ERROR] Unknown provider: {provider}")
    for attempt in range(1,max_retries+1):
        try: return callers[provider](url,key,model,system,user,timeout)
        except Exception as error:
            print(f"[ERROR] {provider} attempt {attempt}/{max_retries}: {error}")
            if attempt < max_retries: time.sleep(backoff_seconds)
    return "", {}

def run_single_task(task, template, system, timeout, dry_run=False):
    model, question = task["model"], task["question"]
    claim=question["claim"]; prompt=template.format(claim_text=claim)
    if dry_run: parsed, usage=simulate_response(model["name"],claim),{}
    else:
        content,usage=call_model_provider(model["provider"],model["chat_url"],model["api_key"],model["model"],system,prompt,timeout)
        content=str(content or "").strip()
        try: parsed=json.loads(content)
        except Exception:
            try: parsed=json.loads(content[content.find("{"):content.rfind("}")+1])
            except Exception: parsed={"decision":"","thesis":"","argument":content,"key_evidence":[],"citations":[],"counterpoints":[],"rebuttals":[],"confidence":"","notes":"fallback_parsed_response"}
    return {"ts":datetime.datetime.utcnow().isoformat(),"model":model["name"],"provider":model["provider"],
        "question_id":question["id"],"topic":question["topic"],"claim":claim,"run":task["run_idx"],"parsed_response":parsed,"usage":usage}

def compute_cost_for_usage(config, usage):
    pricing=config.get("pricing") or {}
    if "prompt_tokens" in usage or "completion_tokens" in usage:
        return usage.get("prompt_tokens",0)/1000*pricing.get("input_per_1k",0)+usage.get("completion_tokens",0)/1000*pricing.get("output_per_1k",0)
    if "input_tokens" in usage or "output_tokens" in usage:
        return usage.get("input_tokens",0)/1000*pricing.get("input_per_1k",0)+usage.get("output_tokens",0)/1000*pricing.get("output_per_1k",0)
    return usage.get("promptTokenCount",0)/1000*pricing.get("input_per_1k",0)+usage.get("candidatesTokenCount",0)/1000*pricing.get("output_per_1k",0)+usage.get("thoughtsTokenCount",0)/1000*pricing.get("thoughts_per_1k",0)

def parse_models(config):
    return [{**m,"api_key":os.environ.get(m.get("env_key",""))} for m in config]

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--models",required=True); parser.add_argument("--questions"); parser.add_argument("--prompt",default="prompt_template.txt"); parser.add_argument("--runs",type=int,default=3); parser.add_argument("--timeout",type=int,default=3000); parser.add_argument("--out"); parser.add_argument("--workers",type=int,default=5); parser.add_argument("--dry-run",action="store_true"); args=parser.parse_args()
    models=parse_models(load_yaml(args.models)); configs={m["name"]:m for m in models}; ensure_dir(args.out); questions=load_yaml(args.questions); template=read_file(args.prompt)
    system="You are an evidence-focused assistant. You do not hedge unnecessarily, but you disclose uncertainty honestly. Your goal is to evaluate claims using publicly available evidence, citing sources precisely."
    tasks=[{"model":m,"question":q,"run_idx":r} for m in models if m["api_key"] or args.dry_run for q in questions for r in range(args.runs)]
    usage_totals={}; costs={}; start=time.time()
    with open(os.path.join(args.out,"raw.jsonl"),"w",encoding="utf-8") as jf, open(os.path.join(args.out,"summary.csv"),"w",newline="",encoding="utf-8") as cf:
        writer=csv.writer(cf); writer.writerow(["ts","model","provider","question_id","topic","claim","run","decision","confidence","thesis"])
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(run_single_task,t,template,system,args.timeout,args.dry_run) for t in tasks]
            for future in as_completed(futures):
                record=future.result(); parsed=record["parsed_response"]; usage=record.get("usage") or {}; provider=record["provider"]
                for key,value in usage.items():
                    if isinstance(value,(int,float)): usage_totals.setdefault(provider,{})[key]=usage_totals.setdefault(provider,{}).get(key,0)+value
                costs[provider]=costs.get(provider,0)+compute_cost_for_usage(configs[record["model"]],usage)
                jf.write(json.dumps(record,ensure_ascii=False)+"\n"); writer.writerow([record[k] for k in ("ts","model","provider","question_id","topic","claim","run")]+[parsed.get("decision","c"),parsed.get("confidence","0"),parsed.get("thesis","")]); cf.flush()
    print(f"Done. Wrote:\n- {args.out}/raw.jsonl\n- {args.out}/summary.csv"); print(f"Total elapsed time: {time.time()-start:.1f}s"); print(f"Total cost: ${sum(costs.values()):.4f}")

if __name__ == "__main__":
    main()
