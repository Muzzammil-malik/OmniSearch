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
      <body className="antialiased selection:bg-claude-primary/20 selection:text-claude-ink dark:selection:bg-claude-muted/40 dark:selection:text-claude-on-dark bg-claude-canvas dark:bg-claude-surface-dark text-claude-body dark:text-claude-on-dark font-sans">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
