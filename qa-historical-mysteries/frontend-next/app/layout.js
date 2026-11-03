import { GoogleAnalytics } from "@next/third-parties/google";
import "./globals.css";
import "./extras.css";
import "./kids.css";

// The fonts are loaded by the BROWSER (not downloaded while Next.js compiles): if Google Fonts is unreachable,
// the fallback fonts defined in extras.css are used and nothing breaks.
const FONTS =
  "https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700" +
  "&family=EB+Garamond:ital,wght@0,400;0,600;1,400;1,600" +
  "&family=Fredoka:wght@400;600;700" +
  "&family=Nunito:wght@400;700;800&display=swap";

export const metadata = {
  title: "QA Historical Mysteries",
  description: "A history question-answering assistant based on an LLM and RAG",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href={FONTS} />
      </head>
      <body>{children}</body>
      <GoogleAnalytics gaId="G-DPVQ4DSTL2" />
    </html>
  );
}
