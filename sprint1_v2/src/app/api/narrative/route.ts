import { NextRequest, NextResponse } from "next/server";
import Groq from "groq-sdk";

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { scenarioResult } = body;

    if (!scenarioResult) {
      return NextResponse.json({ error: "Missing scenarioResult" }, { status: 400 });
    }

    const { headline, interpretation, strengths, watchouts, aircraftLabel, co2Intensity, co2ReductionPct, bmModerate, safCostPremiumPerSeat, safBreakevenCarbonPrice, gapVsRefueleuPp, safTrl } = scenarioResult;

    const systemPrompt = `You are an aviation sustainability analyst writing concise scenario commentary for strategy and executive audiences.
You specialize in SAF (Sustainable Aviation Fuel) economics, ICAO/IATA regulatory frameworks, and carbon pricing.
Write clearly, quantitatively, without hype. Use specific numbers from the data provided.
Avoid marketing language. Flag genuine risks and genuine strengths. Be direct and precise.`;

    const userPrompt = `Analyze this aviation SAF scenario and write a brief structured assessment.

Aircraft: ${aircraftLabel}
CO₂ intensity: ${co2Intensity} gCO₂/RPK (${co2ReductionPct}% below 2019; moderate benchmark: ${bmModerate} gCO₂/RPK)
SAF cost premium: $${safCostPremiumPerSeat.toFixed(2)}/seat (breakeven carbon price: ~$${safBreakevenCarbonPrice}/tCO₂)
ReFuelEU mandate gap: ${gapVsRefueleuPp >= 0 ? "+" : ""}${gapVsRefueleuPp}pp
SAF pathway TRL: ${safTrl}/9

Template headline: ${headline}
Template interpretation: ${interpretation}
Template strengths: ${strengths.join(" | ")}
Template watchouts: ${watchouts.join(" | ")}

Return a JSON object with exactly these keys:
- headline: one concise sentence (max 25 words) stating the scenario's key outcome
- interpretation: 2–3 sentences of precise quantitative context (reference specific numbers)
- strengths: array of 1–3 strings (each 1–2 sentences; cite benchmarks and sources where relevant)
- watchouts: array of 1–3 strings (each 1–2 sentences; be specific about the risk and its magnitude)

Respond ONLY with valid JSON. No markdown, no code fences.`;

    const completion = await groq.chat.completions.create({
      model: "llama-3.3-70b-versatile",
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      temperature: 0.3,
      max_tokens: 600,
    });

    const raw = completion.choices[0]?.message?.content ?? "";

    // Parse and validate the JSON
    let parsed: { headline: string; interpretation: string; strengths: string[]; watchouts: string[] };
    try {
      parsed = JSON.parse(raw);
    } catch {
      // Fallback to template if JSON parse fails
      return NextResponse.json({
        headline: scenarioResult.headline,
        interpretation: scenarioResult.interpretation,
        strengths: scenarioResult.strengths,
        watchouts: scenarioResult.watchouts,
      });
    }

    return NextResponse.json({
      headline: parsed.headline ?? scenarioResult.headline,
      interpretation: parsed.interpretation ?? scenarioResult.interpretation,
      strengths: Array.isArray(parsed.strengths) ? parsed.strengths : scenarioResult.strengths,
      watchouts: Array.isArray(parsed.watchouts) ? parsed.watchouts : scenarioResult.watchouts,
    });
  } catch (err) {
    console.error("Narrative API error:", err);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
