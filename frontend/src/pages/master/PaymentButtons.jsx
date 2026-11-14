import { useI18n } from "../../i18n.jsx";

export const PAYMENT_METHODS = ["cash", "card", "transfer"];

// "Bajarildi"dan oldin to'lov usulini so'raydi: kassa va usta ulushi hisoboti shunga tayanadi.
export default function PaymentButtons({ onPick, onCancel, disabled }) {
  const { t } = useI18n();
  return (
    <div className="row">
      <span className="muted">{t("ms.pay_how")}</span>
      {PAYMENT_METHODS.map((m) => (
        <button key={m} className="btn ghost" disabled={disabled} onClick={() => onPick(m)}>
          {t(`pay.${m}`)}
        </button>
      ))}
      <button className="link" onClick={onCancel}>{t("ms.cancel_pay")}</button>
    </div>
  );
}
