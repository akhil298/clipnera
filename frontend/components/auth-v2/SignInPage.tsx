import { SignInPanel } from './SignInPanel';

export type SignInSearchParams = Promise<Record<string, string | string[] | undefined>>;

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value) ?? null;

/** `/login` and `/signup` render this same page (screens/01 §3, open question Q2). */
export async function SignInPage({ searchParams }: { searchParams: SignInSearchParams }) {
  const params = await searchParams;
  return <SignInPanel next={first(params.next)} expired={first(params.reason) === 'expired'} />;
}
