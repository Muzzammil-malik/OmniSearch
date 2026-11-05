import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "OmniSearch",
  description: "One search. Your entire digital world.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased selection:bg-cyan-500/20 selection:text-cyan-300">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
