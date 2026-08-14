import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Universal Data Normalizer & JSON Exporter",
  description:
    "AI-powered normalization of inconsistent Excel, CSV, and JSON data into a standardized target JSON schema.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background antialiased">{children}</body>
    </html>
  );
}
