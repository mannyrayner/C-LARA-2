#!/usr/bin/env python3
"""Detailed analysis of experiment summary.csv."""
import ast, json, os, sys
from datetime import datetime
import numpy as np
import pandas as pd

def safe_parse(value):
    if pd.isna(value): return {}
    if isinstance(value, dict): return value
    try: return json.loads(value)
    except Exception:
        try: return ast.literal_eval(value)
        except Exception: return {}

def main():
    if len(sys.argv) < 3:
        print("Usage: python analysis_script.py /path/to/summary.csv /path/to/output_dir"); raise SystemExit(1)
    source, out_dir=sys.argv[1:3]; os.makedirs(out_dir,exist_ok=True); df=pd.read_csv(source)
    def norm(value):
        if pd.isna(value): return "c"
        value=str(value).strip().lower(); return value[0] if value and value[0] in "abc" else value
    df["decision"]=(df["decision"] if "decision" in df else "c").apply(norm)
    df["confidence"]=pd.to_numeric(df["confidence"],errors="coerce") if "confidence" in df else np.nan
    df["thesis"]=(df["thesis"] if "thesis" in df else "").fillna("").astype(str)
    counts=df.groupby(["model","decision"]).size().unstack(fill_value=0); counts["total"]=counts.sum(axis=1)
    unique=df.groupby(["question_id","model"])["decision"].agg(lambda s:",".join(sorted(set(s)))).reset_index()
    wide=unique.pivot(index="question_id",columns="model",values="decision").fillna("")
    decisions=wide.apply(lambda row:[v for v in row if v!=""],axis=1)
    agreement=pd.DataFrame({"question_id":wide.index,"agree":decisions.apply(lambda v:bool(v) and all("," not in x for x in v) and len(set(v))==1),"value":decisions}).reset_index(drop=True)
    conf=df.dropna(subset=["confidence"])
    conf_stats=conf.groupby(["model","question_id"])["confidence"].agg(["mean","std","count"]).reset_index().rename(columns={"mean":"mean_confidence","std":"std_confidence","count":"n"})
    def majority(series):
        vals=[x for x in series if x in "abc"]
        if not vals:return ""
        c=pd.Series(vals).value_counts(); return "".join(sorted(c[c==c.max()].index))
    maj=df.groupby(["model","question_id"])["decision"].apply(majority).reset_index(name="majority_decision")
    conf_stats=conf_stats.merge(maj,on=["model","question_id"],how="left")
    avg=conf.groupby("model")["confidence"].agg(["mean","std","count"]).reset_index().rename(columns={"mean":"mean_confidence","std":"std_confidence","count":"n"})
    pivot=conf_stats.pivot(index="question_id",columns="model",values="mean_confidence").sort_index().fillna("")
    consistency=df.groupby(["model","question_id"])["decision"].nunique().reset_index(name="unique_decisions"); consistency["consistent"]=consistency.unique_decisions==1
    first=df.sort_values(["model","question_id","run"]).groupby(["model","question_id"]).first().reset_index()[["model","question_id","thesis"]]
    collapsed=df.groupby(["question_id","model"])["decision"].agg(lambda s:pd.Series(s).value_counts().idxmax()).unstack()
    unanimous=df.groupby(["question_id","model"])["decision"].nunique().eq(1).unstack()
    outputs={"decision_counts_by_model.csv":counts,"per_question_decisions_wide.csv":wide,"agreement_by_question.csv":agreement,"conf_stats_by_model_question.csv":conf_stats,"conf_mean_by_question_model.csv":pivot,"avg_conf_by_model.csv":avg,"consistency_by_model_question.csv":consistency,"first_thesis_samples.csv":first,"majority_decisions_wide.csv":collapsed,"unanimity_wide.csv":unanimous}
    for name,frame in outputs.items(): frame.to_csv(os.path.join(out_dir,name),index=name in {"agreement_by_question.csv","conf_stats_by_model_question.csv","avg_conf_by_model.csv","consistency_by_model_question.csv","first_thesis_samples.csv"})
    report="\n".join(["Experiment detailed analysis report",f"Generated: {datetime.utcnow().isoformat()} UTC","","Decision counts:",counts.to_string(),"","Agreement:",agreement.to_string(index=False),"","Average confidence:",avg.to_string(index=False),"","Per-question confidence:",pivot.to_string()])
    open(os.path.join(out_dir,"analysis_report.txt"),"w",encoding="utf-8").write(report)
    summary={"n_questions":len(wide),"agree_questions":agreement.loc[agreement.agree,"question_id"].tolist(),"disagree_questions":agreement.loc[~agreement.agree,"question_id"].tolist(),"counts_by_model":counts.to_dict()}
    json.dump(summary,open(os.path.join(out_dir,"short_summary.json"),"w",encoding="utf-8"),indent=2)
    print(report)
if __name__=="__main__": main()
