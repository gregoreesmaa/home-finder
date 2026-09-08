import type { Metadata } from "next";

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
