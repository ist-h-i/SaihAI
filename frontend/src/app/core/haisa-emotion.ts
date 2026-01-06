export type HaisaSpeechTone = 'neutral' | 'info' | 'success' | 'warning' | 'error';

export type HaisaEmotion =
  | 'standard'
  | 'hope'
  | 'joy'
  | 'relief'
  | 'anxiety'
  | 'energy'
  | 'effort'
  | 'haste'
  | 'explosion';

export const HAISA_ASSET_DIR = '/assets/saihaikun' as const;

export const HAISA_EMOTION_LABELS: Record<HaisaEmotion, string> = {
  standard: '通常',
  hope: '期待',
  joy: '喜び',
  relief: '安心',
  anxiety: '不安',
  energy: '活力',
  effort: '決意',
  haste: '焦り',
  explosion: '爆発',
};

export const HAISA_IMAGE_BY_EMOTION: Record<HaisaEmotion, string> = {
  standard: 'standard.png',
  hope: 'hope.png',
  joy: 'joy.png',
  relief: 'relief.png',
  anxiety: 'anxiety.png',
  energy: 'energy.png',
  effort: 'effort.png',
  haste: 'haste.png',
  explosion: 'explosion.png',
};

export const DEFAULT_EMOTION_BY_TONE: Record<HaisaSpeechTone, HaisaEmotion> = {
  neutral: 'standard',
  info: 'hope',
  success: 'relief',
  warning: 'haste',
  error: 'anxiety',
};

export function resolveHaisaEmotion(
  tone: HaisaSpeechTone,
  emotion?: HaisaEmotion
): HaisaEmotion {
  return emotion ?? DEFAULT_EMOTION_BY_TONE[tone] ?? 'standard';
}

export function haisaEmotionLabel(emotion: HaisaEmotion): string {
  return HAISA_EMOTION_LABELS[emotion];
}

export function haisaAvatarSrc(emotion: HaisaEmotion): string {
  const file = HAISA_IMAGE_BY_EMOTION[emotion] ?? HAISA_IMAGE_BY_EMOTION.standard;
  return `${HAISA_ASSET_DIR}/${file}`;
}

export function haisaEmotionForRisk(riskPct: number): HaisaEmotion {
  if (riskPct >= 85) return 'explosion';
  if (riskPct >= 70) return 'haste';
  if (riskPct >= 55) return 'anxiety';
  return 'relief';
}

export function haisaEmotionForFit(fitPct: number): HaisaEmotion {
  if (fitPct >= 80) return 'joy';
  if (fitPct >= 65) return 'hope';
  if (fitPct >= 45) return 'energy';
  return 'effort';
}
