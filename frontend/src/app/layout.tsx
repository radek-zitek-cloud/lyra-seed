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
      <body style={{ display: "flex", flexDirection: "column", height: "100vh", margin: 0, overflow: "hidden" }}>
        <header
          style={{
            padding: "8px 20px",
            borderBottom: "1px solid #1a1a1a",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexShrink: 0,
          }}
        >
          <a
            href="/"
            style={{
              fontSize: "16px",
              fontWeight: 700,
              color: "#e0e0e0",
              letterSpacing: "2px",
              textDecoration: "none",
            }}
          >
            LYRA<span className="cursor" />
          </a>
          <nav style={{ display: "flex", gap: "16px", fontSize: "11px" }}>
            <a
              href="/"
              style={{
                color: "#555",
                textDecoration: "none",
                border: "1px solid #222",
                borderRadius: "2px",
                padding: "3px 10px",
              }}
            >
              AGENTS
            </a>
            <a
              href="/memories"
              style={{
                color: "#555",
                textDecoration: "none",
                border: "1px solid #222",
                borderRadius: "2px",
                padding: "3px 10px",
              }}
            >
              MEMORIES
            </a>
          </nav>
        </header>
        <main style={{ padding: "8px 12px", flex: 1, minHeight: 0, overflow: "auto" }}>{children}</main>
      </body>
    </html>
  );
}
