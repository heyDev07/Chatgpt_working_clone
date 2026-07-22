import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <LoginForm />
    </main>
  );
}
