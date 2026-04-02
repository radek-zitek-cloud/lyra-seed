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
      <body>
        <header
          style={{
            padding: "12px 20px",
            borderBottom: "1px solid #1a1a1a",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <a
            href="/"
            style={{
              fontSize: "18px",
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
                padding: "4px 10px",
              }}
            >
              AGENTS
            </a>
          </nav>
        </header>
        <main style={{ padding: "12px 20px" }}>{children}</main>
        <footer
          style={{
            padding: "8px 20px",
            borderTop: "1px solid #1a1a1a",
            fontSize: "11px",
            color: "#333",
            textAlign: "center",
          }}
        >
          Lyra Agent Platform v0.1
        </footer>
      </body>
    </html>
  );
}
