export const metadata = {
  title: "Lyra — Agent Platform",
  description: "Self-evolving multi-agent observation UI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
