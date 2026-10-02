import type { Metadata } from 'next';
import EditorLanding from '@/components/editor-landing/EditorLanding';

export const metadata: Metadata = {
  title: 'Clipnera Editor · Describe it, we cut it',
  description: 'Drop in footage, say what you want, and edit the result on a real timeline.',
};

export default function EditorPage() {
  return <EditorLanding />;
}
