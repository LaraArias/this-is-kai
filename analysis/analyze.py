#!/usr/bin/env python3
"""What moves the tokens-per-second score? A pandas pass over every model call we recorded.

Input:  data/runs.csv (one row per agent run), data/calls.csv (one row per model call).
Output: analysis/REPORT.md.   Run:  python3 analysis/analyze.py

Every call's rate is server-reported: completion tokens / completion time, as read by the
hackathon's official speed patch. The run score is the arithmetic mean of its calls' rates.
These are observational runs, not controlled experiments: prompts, stores, queue load and
time of day changed between them. The tables show where speed differs, not why.
"""
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
runs = pd.read_csv(ROOT / "data" / "runs.csv")
calls = pd.read_csv(ROOT / "data" / "calls.csv")
FINISHED = {"completed", "verified", "baseline_verified"}
runs["finished"] = runs["status"].isin(FINISHED)
calls["kind"] = np.where(calls["stop_reason"] == "toolUse", "tool call", "final answer")
calls["where"] = np.select([calls["position"] == 1, calls["position"] == calls["n_calls"]], ["first", "last"], "middle")
out = []


def table(df, floats=1):
    return df.to_markdown(floatfmt=f".{floats}f")


def section(title, intro, df, floats=1, after=""):
    out.append(f"## {title}\n\n{intro}\n\n{table(df, floats)}\n" + (f"\n{after}\n" if after else ""))


def stats(g):
    return g["tps"].agg(calls="count", median="median", mean="mean", p10=lambda s: s.quantile(0.1), p90=lambda s: s.quantile(0.9))


# 1. What is in the data
overview = runs.groupby("family").agg(runs=("run", "count"), finished=("finished", "sum"), calls=("n_calls", "sum"),
                                      median_calls_per_run=("n_calls", "median"), median_wall_s=("wall_seconds", "median"),
                                      median_score=("mean_tps", "median"))
section("1. What is in the data",
        f"{len(runs)} agent runs and {len(calls)} model calls, all Kimi K3.1 Pro on Cerebras through OpenClaw. "
        "`browsing` runs let the agent find products by opening store pages; `catalog` runs name one store's live search endpoint in the prompt.",
        overview)

# 2. Tool calls against final answers
section("2. Rate by how the call ended",
        "Per-call rate by how the call ended.", stats(calls.groupby("kind")))

# 3. Output length
bins = [0, 60, 120, 250, 500, 1000, 100000]
labels = ["1-60", "61-120", "121-250", "251-500", "501-1000", "1001+"]
calls["tokens"] = pd.cut(calls["output_tokens"], bins=bins, labels=labels)
by_len = stats(calls.groupby("tokens", observed=True))
rho = calls[["output_tokens", "tps"]].corr(method="spearman").iloc[0, 1]
section("3. Rate by output length", "Per-call rate by number of output tokens (reasoning tokens included).", by_len,
        after=f"Spearman correlation between output tokens and rate across all calls: {rho:.2f}.")

# 4. Length and kind together
both = calls.pivot_table(index="tokens", columns="kind", values="tps", aggfunc=["median", "count"], observed=True)
section("4. Length and kind are tangled", "Median rate and number of calls for each combination. Empty cells have no calls.", both)

# 5. Position in the run
section("5. Rate by position in the run", "First call, last call, everything between.", stats(calls.groupby("where")))

# 6. A linear description (not a causal model)
X = np.column_stack([np.ones(len(calls)), np.log(calls["output_tokens"]), (calls["kind"] == "tool call").astype(float),
                     (calls["where"] == "first").astype(float), (calls["family"] == "catalog").astype(float)])
y = calls["tps"].to_numpy()
coef, *_ = np.linalg.lstsq(X, y, rcond=None)
r2 = 1 - ((y - X @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
fit = pd.DataFrame({"coefficient (tokens/s)": coef}, index=["intercept", "log(output tokens)", "is a tool call", "is the first call", "is a catalog run"])
section("6. How much of the spread these labels describe",
        "Ordinary least squares of per-call rate on four labels. It describes this sample; it is not a causal estimate.", fit,
        after=f"R² = {r2:.2f}: the labels account for about {r2:.0%} of the variance between calls. The rest is not explained by anything recorded here.")

# 7. How the score is built
fin = runs[runs["finished"]].copy()
fin["token_weighted_tps"] = fin["output_tokens"] / fin["generation_seconds"]
fin["tool_share"] = fin["run"].map(calls.groupby("run")["kind"].apply(lambda s: (s == "tool call").mean()))
c1 = fin[["n_calls", "mean_tps"]].corr(method="spearman").iloc[0, 1]
c2 = fin[["tool_share", "mean_tps"]].corr(method="spearman").iloc[0, 1]
c3 = fin[["wall_seconds", "mean_tps"]].corr(method="spearman").iloc[0, 1]
top = fin.sort_values("mean_tps", ascending=False).head(8)[["run", "family", "n_calls", "tool_share", "mean_tps", "token_weighted_tps", "wall_seconds", "generation_seconds"]].set_index("run")
section("7. The score is a mean of calls: the top runs",
        "The eight highest-scoring finished runs. `mean_tps` is the official score; `token_weighted_tps` is total tokens over total generation time.",
        top, floats=2,
        after=f"Across the {len(fin)} finished runs, Spearman correlation of the score with the number of calls is {c1:.2f}, "
              f"with the share of tool calls {c2:.2f}, and with how long the whole run took {c3:.2f}.")

# 8. Time: generation against the whole run
fin["generation_share_%"] = 100 * fin["generation_seconds"] / fin["wall_seconds"]
time = fin.groupby("family").agg(runs=("run", "count"), median_wall_s=("wall_seconds", "median"), min_wall_s=("wall_seconds", "min"),
                                 max_wall_s=("wall_seconds", "max"), median_generation_s=("generation_seconds", "median"),
                                 median_generation_share=("generation_share_%", "median"))
section("8. Where the time goes", "Finished runs. Generation is the summed server-reported completion time of all calls in the run.", time, floats=2)

# 9. Rejected requests and the clock
cat = runs[runs["family"] == "catalog"][["run", "temperature", "status", "http_429", "wall_seconds", "n_calls", "generation_seconds", "mean_tps"]].set_index("run")
okc = runs[(runs["family"] == "catalog") & runs["finished"]]
c4 = okc[["http_429", "wall_seconds"]].corr(method="spearman").iloc[0, 1]
c5 = okc[["http_429", "mean_tps"]].corr(method="spearman").iloc[0, 1]
section("9. Catalog runs: rejected requests, the clock and the score",
        "All catalog runs, same prompt. `http_429` counts rate-limit rejections logged during the run.", cat, floats=2,
        after=f"Among the {len(okc)} that finished, Spearman correlation of rejections with whole-run time is {c4:.2f} and with the score {c5:.2f}.")

# 10. Temperature
temp = okc.groupby("temperature").agg(runs=("run", "count"), min_score=("mean_tps", "min"), median_score=("mean_tps", "median"), max_score=("mean_tps", "max"))
section("10. Temperature 0 against 1 on the catalog prompt", "Finished catalog runs only.", temp,
        after="The two ranges overlap. With this few runs there is no demonstrated effect.")

head = ("# What moves the tokens-per-second score\n\n"
        "Generated by `analysis/analyze.py` from `data/runs.csv` and `data/calls.csv`. Do not edit by hand.\n\n"
        "Every rate here is server-reported (completion tokens over completion time) for Kimi K3.1 Pro on Cerebras through OpenClaw. "
        "These runs were not controlled experiments: prompts, stores, queue load and time of day changed between them. "
        "The tables show where speed differs. They do not show why.\n")
(ROOT / "analysis" / "REPORT.md").write_text(head + "\n" + "\n".join(out))
print("wrote analysis/REPORT.md")
