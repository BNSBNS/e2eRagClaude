import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { SessionProvider } from './providers/SessionProvider';
import { QueryProvider } from './providers/QueryProvider';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'AI Document Processing Platform',
  description: 'Production-grade RAG application with intelligent document processing',
  keywords: ['AI', 'document processing', 'RAG', 'machine learning', 'NextJS'],
  authors: [{ name: 'AI Platform Team' }],
  viewport: 'width=device-width, initial-scale=1',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <SessionProvider>
          <QueryProvider>
            {children}
          </QueryProvider>
        </SessionProvider>
      </body>
    </html>
  );
}