import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "home-finder",
  description: "Eesti kodud järjestatud: elamiskvaliteet + hinna õiglus.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="et">
      <body>{children}</body>
    </html>
  );
}
