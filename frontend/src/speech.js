// AI javobini ovozli o'qish.
// 1) Server TTS (/api/ai/speak/): sifatli, o'zbek tilini ham biladi. .env da TTS_PROVIDER sozlangan bo'lsa ishlaydi.
// 2) Server sozlanmagan (503) yoki xato bo'lsa — brauzerning o'z ovozi (speechSynthesis).
import { api } from "./api.js";

const BCP47 = { uz: "uz-UZ", ru: "ru-RU", en: "en-US" };
let current = null; // { audio, url } yoki { utter }
let token = 0;

const hasCyrillic = (s) => (s.match(/[А-Яа-яЁё]/g) || []).length > s.length * 0.3;

export function stopSpeaking() {
  token += 1;
  if (current?.audio) {
    current.audio.pause();
    URL.revokeObjectURL(current.url);
  }
  window.speechSynthesis?.cancel();
  current = null;
}

function pickVoice(lang) {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  const want = lang.toLowerCase();
  const prefix = want.slice(0, 2);
  const byLang = (l) => voices.find((v) => v.lang.toLowerCase().replace("_", "-").startsWith(l));
  // O'zbekcha ovoz ko'p qurilmada yo'q: lotin yozuvi turkcha o'qilishga yaqin, shuning uchun turk ovozi zaxira
  return byLang(want) || byLang(prefix) || (prefix === "uz" ? byLang("tr") : null) || null;
}

function browserSpeak(text, uiLang, onEnd) {
  const synth = window.speechSynthesis;
  if (!synth) return false;
  const lang = hasCyrillic(text) ? BCP47.ru : BCP47[uiLang] || BCP47.uz;
  const voice = pickVoice(lang);
  if (!voice) return false;
  const utter = new SpeechSynthesisUtterance(text);
  utter.voice = voice;
  utter.lang = voice.lang;
  utter.onend = utter.onerror = () => onEnd?.();
  synth.cancel();
  current = { utter };
  synth.speak(utter);
  return true;
}

/** Matnni o'qiydi. Qaytaradi: "server" | "browser". Ovoz topilmasa Error("no_voice") tashlaydi. */
export async function speak(text, uiLang, onEnd) {
  stopSpeaking();
  const mine = token;
  try {
    const blob = await api("/api/ai/speak/", { method: "POST", body: { text, format: "mp3" }, blob: true });
    if (mine !== token) return "server"; // kutish paytida to'xtatilgan
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = audio.onerror = () => {
      URL.revokeObjectURL(url);
      if (current?.audio === audio) current = null;
      onEnd?.();
    };
    current = { audio, url };
    await audio.play(); // brauzer avtoo'ynashni bloklasa NotAllowedError tashlaydi
    return "server";
  } catch (err) {
    if (err?.name === "NotAllowedError") throw err;
    if (err?.status && err.status !== 503 && err.status !== 502 && err.status !== 429) throw err;
  }
  if (mine !== token) return "browser";
  if (!browserSpeak(text, uiLang, onEnd)) throw new Error("no_voice");
  return "browser";
}
