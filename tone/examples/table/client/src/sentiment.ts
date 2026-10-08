/**
 * Sentiment, not identity: the colour of every meter and badge that reads a line. Character colours
 * stay on names, dots, borders and the voice. These four say how a thing feels.
 */

export type Sentiment = "hostile" | "cold" | "neutral" | "warm"

export const SENTIMENT_COLOR: Record<Sentiment, string> = {
  hostile: "var(--color-hostile)",
  cold: "var(--color-cold)",
  neutral: "var(--color-muted-foreground)",
  warm: "var(--color-warm)",
}

const ACT_SENTIMENT: Record<string, Sentiment> = {
  insult: "hostile",
  threat: "hostile",
  accusation: "hostile",
  demand: "cold",
  dismiss: "cold",
  refusal: "cold",
  tease: "cold",
  warning: "neutral",
  request: "neutral",
  none: "neutral",
  thanks: "warm",
  praise: "warm",
  apology: "warm",
  comfort: "warm",
}

const EMOTION_SENTIMENT: Record<string, Sentiment> = {
  angry: "hostile",
  disgusted: "hostile",
  contemptuous: "hostile",
  sad: "cold",
  afraid: "cold",
  neutral: "neutral",
  surprised: "neutral",
  happy: "warm",
  amused: "warm",
}

export function actSentiment(act: string, hostile = false): Sentiment {
  return hostile ? "hostile" : (ACT_SENTIMENT[act] ?? "neutral")
}

export function emotionSentiment(emotion: string): Sentiment {
  return EMOTION_SENTIMENT[emotion] ?? "neutral"
}

/** A heart's colour by its level: red when nearly gone, amber when cool, grey in the middle, green when warm. */
export function heartSentiment(value: number): Sentiment {
  if (value < 25) return "hostile"
  if (value < 45) return "cold"
  if (value < 60) return "neutral"
  return "warm"
}

/** Plain words for a heart's level, for the cards. */
export function heartWord(value: number): string {
  if (value < 25) return "had enough of you"
  if (value < 45) return "wary of you"
  if (value < 60) return "no strong feelings"
  if (value < 80) return "warm toward you"
  return "likes you a lot"
}
