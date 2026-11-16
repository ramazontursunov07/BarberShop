// Ichki SVG ikonalar (tashqi kutubxonasiz). <Icon name="home" size={20} />
const P = {
  home: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  scissors: "M6 9a3 3 0 100-6 3 3 0 000 6zM6 21a3 3 0 100-6 3 3 0 000 6zM20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 4-6 8-6s8 2 8 6",
  search: "M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3",
  pin: "M12 21s7-6.2 7-12a7 7 0 10-14 0c0 5.8 7 12 7 12zM12 11.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z",
  phone: "M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z",
  clock: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  mic: "M12 15a3 3 0 003-3V6a3 3 0 00-6 0v6a3 3 0 003 3zM6 11a6 6 0 0012 0M12 17v4",
  send: "M4 12l16-8-6 16-3-7z",
  camera: "M4 8h3l2-3h6l2 3h3v12H4zM12 17a4 4 0 100-8 4 4 0 000 8z",
  sun: "M12 16a4 4 0 100-8 4 4 0 000 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z",
  check: "M5 12.5l4.5 4.5L19 7.5",
  gift: "M4 10h16v10H4zM3 7h18v3H3zM12 7v13M12 7c-2 0-4-1-4-2.5S10 2 12 7zM12 7c2 0 4-1 4-2.5S14 2 12 7z",
  tag: "M3 12V4h8l10 10-8 8zM7.5 8.5h.01",
  bag: "M5 8h14l-1 12H6zM9 8a3 3 0 016 0",
  repeat: "M17 2l4 4-4 4M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 01-3 3H3",
  users: "M9 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM2 20c0-3.3 3.1-5 7-5s7 1.7 7 5M17 4.3a3.5 3.5 0 010 6.4M22 20c0-2.5-1.8-4.1-4.5-4.7",
  logout: "M9 4H5v16h4M16 8l4 4-4 4M20 12H9",
  settings: "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12a7 7 0 00-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 00-2-1.2L14 3h-4l-.4 2.6a7 7 0 00-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 005 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 002 1.2L10 21h4l.4-2.6a7 7 0 002-1.2l2.4 1 2-3.4-2-1.6c.1-.4.2-.8.2-1.2z",
  arrow: "M5 12h14M13 6l6 6-6 6",
  close: "M6 6l12 12M18 6L6 18",
  nav: "M3 11l18-8-8 18-2-8z",
  scan: "M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4M8 12h8",
  coffee: "M5 8h12v6a5 5 0 01-5 5H10a5 5 0 01-5-5zM17 10h2a2 2 0 010 4h-2M8 2v3M12 2v3",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  chat: "M4 5h16v11H9l-5 4z",
  eye: "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 15a3 3 0 100-6 3 3 0 000 6z",
  eyeoff: "M3 3l18 18M10.6 5.1A10 10 0 0112 5c6.4 0 10 7 10 7a17 17 0 01-3.2 4M6.6 6.7C3.9 8.4 2 12 2 12s3.6 7 10 7c1.7 0 3.2-.4 4.5-1M9.9 9.9a3 3 0 004.2 4.2",
  edit: "M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4",
};

export default function Icon({ name, size = 20, stroke = 1.9, fill = "none", ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      <path d={P[name] || P.star} />
    </svg>
  );
}
