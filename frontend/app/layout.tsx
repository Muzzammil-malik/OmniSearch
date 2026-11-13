import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "OmniSearch — Local File & Document Search",
  description: "Everything on your computer, intelligently searchable.",
  icons: {
    icon: "/assets/OmniSearch_Logo.png",
    apple: "/assets/OmniSearch_Logo.png",
  },
  openGraph: {
    title: "OmniSearch — Local File & Document Search",
    description: "Everything on your computer, intelligently searchable.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased font-sans selection:bg-[#4A5C6A]/30 selection:text-[#06141B] dark:selection:bg-[#4A5C6A] dark:selection:text-[#CCD0CF]">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
