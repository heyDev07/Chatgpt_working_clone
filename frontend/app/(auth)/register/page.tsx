import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-2xl font-semibold">Create your account</h1>
      <RegisterForm />
    </main>
  );
}
