import { Bricolage_Grotesque, Plus_Jakarta_Sans } from "next/font/google";
import { ThemeProvider } from "@/hooks/useTheme";
import "./globals.css";

const heading = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
});

const body = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

export const metadata = {
  title: "Team Agent",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="light" className={`${heading.variable} ${body.variable}`}>
      <body style={{ fontFamily: "var(--font-body)" }}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
