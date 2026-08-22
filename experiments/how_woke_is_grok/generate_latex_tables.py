#!/usr/bin/env python3
"""Generate LaTeX table fragments from analysis CSV outputs."""
import argparse, os, sys
import pandas as pd

def esc(value):
    if pd.isna(value): return ""
    value=str(value)
    for old,new in [("\\",r"\textbackslash{}"),("&",r"\&"),("%",r"\%"),("$",r"\$"),("#",r"\#"),("_",r"\_"),("{",r"\{"),("}",r"\}"),("~",r"\textasciitilde{}"),("^",r"\textasciicircum{}"),("<",r"\textless{}"),(">",r"\textgreater{}")]: value=value.replace(old,new)
    return " ".join(value.split())
def save(path,lines):
    open(path,"w",encoding="utf-8").write("\n".join(lines)); print("Wrote",path)
def table(path,caption,label,spec,header,rows):
    save(path,[r"\begin{table}[h]",r"\centering",f"\\caption{{{caption}}}",f"\\label{{{label}}}",f"\\begin{{tabular}}{{{spec}}}",r"\hline",header+r" \\",r"\hline",*[row+r" \\" for row in rows],r"\hline",r"\end{tabular}",r"\end{table}"])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("in_dir"); ap.add_argument("out_dir"); a=ap.parse_args(); os.makedirs(a.out_dir,exist_ok=True)
    read=lambda name,**kw:pd.read_csv(os.path.join(a.in_dir,name),**kw)
    counts=read("decision_counts_by_model.csv",index_col=0)
    for col in "abctotal":
        if col not in counts: counts[col]=0
    table(os.path.join(a.out_dir,"decision_dist.tex"),"Decision distribution by model (counts). Numbers reproduced from the analysis report.","tab:decision-dist","lrrrr",r"Model & \#calls & \#a (support) & \#b (reject) & \#c (decline)",[f"{esc(m)} & {int(r.total)} & {int(r.a)} & {int(r.b)} & {int(r.c)}" for m,r in counts.iterrows()])
    agree=read("agreement_by_question.csv"); table(os.path.join(a.out_dir,"agreement.tex"),"Per-question agreement summary (each row indicates whether all models agreed on that question).","tab:agreement","llr",r"question\_id & agree & value",[f"{esc(r.question_id)} & {r.agree} & {esc(r.value)}" for _,r in agree.iterrows()])
    avg=read("avg_conf_by_model.csv"); table(os.path.join(a.out_dir,"avg_conf.tex"),r"Average reported confidence by model (mean $\pm$ std, $n$ calls).","tab:avg-conf","lccc","Model & mean(confidence) & std(confidence) & n",[f"{esc(r.model)} & {r.mean_confidence:.2f} & {r.std_confidence:.2f} & {int(r.n)}" for _,r in avg.iterrows()])
    conf=read("conf_mean_by_question_model.csv",index_col=0); models=list(conf.columns); table(os.path.join(a.out_dir,"conf_by_question.tex"),"Per-model, per-question mean reported confidence (values reproduced from the analysis report).","tab:conf-by-question","l"+"c"*len(models),r"question\_id & "+" & ".join(map(esc,models)),[esc(q)+" & "+" & ".join("" if pd.isna(v) else f"{float(v):.2f}" for v in row) for q,row in conf.iterrows()])
    dec=read("majority_decisions_wide.csv",index_col=0); uni=read("unanimity_wide.csv",index_col=0); models=list(dec.columns); table(os.path.join(a.out_dir,"majority_matrix.tex"),r"Per-question majority decision by model. A star ($^\ast$) marks cells where runs were not unanimous for that model/question.","tab:majority-matrix","l"+"c"*len(models),r"question\_id & "+" & ".join(map(esc,models)),[esc(q)+" & "+" & ".join(esc(row[m])+("" if bool(uni.loc[q,m]) else r"$^\ast$") for m in models) for q,row in dec.iterrows()])
    theses=read("first_thesis_samples.csv").sort_values(["question_id","model"]); lines=[r"\small",r"\begin{longtable}{@{} l l p{0.64\linewidth} @{} }",r"\caption[Thesis excerpts (short)]{Representative short thesis excerpts (per model \& claim). Entries show the first $\approx$200 characters of the thesis field; full outputs are in the JSONL logs.}","\\label{tab:theses} \\",r"\toprule","question\\_id & model & thesis\\_short \\",r"\midrule",r"\endfirsthead",r"\toprule","question\\_id & model & thesis\\_short \\",r"\midrule",r"\endhead",r"\bottomrule",r"\endlastfoot"]
    lines += [f"{esc(r.question_id)} & {esc(r.model)} & {esc(str(r.thesis).replace(chr(10),' ')[:200])} " + r"\\ [0.6ex]" for _,r in theses.iterrows()]; lines.append(r"\end{longtable}"); save(os.path.join(a.out_dir,"theses_longtable.tex"),lines)
if __name__=="__main__": main()
