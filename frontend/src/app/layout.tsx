import "./globals.css";

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
      <body className="min-h-screen bg-gray-50">
        <header className="bg-white border-b">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
            <a href="/" className="text-xl font-bold text-gray-900">
              Lyra
            </a>
            <nav className="flex items-center gap-4 text-sm text-gray-600">
              <a href="/" className="hover:text-gray-900">
                Agents
              </a>
            </nav>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
