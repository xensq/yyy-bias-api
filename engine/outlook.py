import os
import json

def generate_outlook(macro, bias, topology, entropy):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"text": None, "error": "ANTHROPIC_API_KEY not set on Railway"}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        regime    = topology.get("regime", "UNKNOWN")
        pca1      = topology.get("pca1", 0)
        pca2      = topology.get("pca2", 0)
        dist      = topology.get("dist", 0)
        aligned   = topology.get("aligned", False)
        direction = bias.get("direction", "NEUTRAL")
        conviction= bias.get("conviction", 0)
        size_rule = bias.get("size_rule", "UNKNOWN")
        narrative = bias.get("narrative", "")
        ent_status= entropy.get("status", "NORMAL")
        ent_rho   = entropy.get("rho", 0)
        walcl_note= macro.get("walcl", {}).get("note", "")
        res_note  = macro.get("reserves_rrp", {}).get("note", "")
        oas_note  = macro.get("oas", {}).get("note", "")
        oas_val   = macro.get("oas", {}).get("value", 0)
        auctions  = macro.get("auctions", {})
        auction_note = auctions.get("note", "") if auctions.get("warning") else "No major auctions this week."

        prompt = f"""You are a senior market analyst writing a professional nightly market outlook. Write 3 concise paragraphs covering:
1. The macro and liquidity environment based on the data
2. What the structural signals (topology/entropy) mean for tomorrow
3. The practical trading implications and what to watch

Use specific numbers from the data. Be direct and confident. Write for experienced derivatives traders. No bullet points, no headers, flowing prose only. Be concise — 80-100 words per paragraph max.

DATA:
Bias: {direction} | Conviction: {conviction:.0f}% | Size: {size_rule}
Narrative: {narrative}
Topology regime: {regime} | PCA1 trend: {pca1:+.3f} | PCA2 momentum: {pca2:+.3f} | Dist: {dist:.3f} | Aligned: {aligned}
Entropy: {ent_status} | vs threshold: {ent_rho:.3f}x
Fed balance sheet: {walcl_note}
Reserves/RRP: {res_note}
OAS credit spreads: {oas_note} (current: {oas_val:.2f}%)
Treasury auctions: {auction_note}

Write the outlook:"""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return {"text": msg.content[0].text.strip(), "error": None}
    except Exception as e:
        return {"text": None, "error": str(e)}
