import { useI18n } from "../../i18n.jsx";

// Yangi akkaunt uchun vaqtinchalik parol: faqat yaratilgan zahoti bir marta ko'rsatiladi.
export default function TempPassword({ phone, password }) {
  const { t } = useI18n();
  if (!password) return null;
  return (
    <div className="card summary">
      <p>{t("adm.temp_password")}</p>
      <p>
        {t("adm.login_phone")}: <strong>{phone}</strong>
      </p>
      <p>
        {t("password")}: <strong style={{ fontFamily: "monospace", userSelect: "all" }}>{password}</strong>
      </p>
    </div>
  );
}
