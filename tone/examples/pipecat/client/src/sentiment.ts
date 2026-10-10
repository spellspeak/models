/**
 * Sentiment, not identity: the colour of every meter and badge that reads a line. Character colours
 * stay on names, dots, borders and the voice. These four say how a thing feels.
 */

export type Sentiment = "hostile" | "cold" | "neutral" | "warm"

export const SENTIMENT_COLOR: Record<Sentiment, string> = {
  hostile: "var(--color-hostile)",
  cold: "var(--color-cold)",
  neutral: "var(--color-neutral)",
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

/** A feeling's colour by its level: red when nearly gone, amber when cool, grey in the middle, green when warm. */
export function feelingSentiment(value: number): Sentiment {
  if (value < 25) return "hostile"
  if (value < 45) return "cold"
  if (value < 60) return "neutral"
  return "warm"
}

/** A feeling in a word, by the same bands the characters are told (server/feelings.py). */
export function feelingWord(value: number): string {
  if (value < 25) return "hostile"
  if (value < 45) return "wary"
  if (value < 60) return "neutral"
  if (value < 80) return "warm"
  return "devoted"
}
