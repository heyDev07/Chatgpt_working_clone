"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthContext";

const schema = z.object({
  fullName: z.string().max(255).optional(),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type FormValues = z.infer<typeof schema>;

export function RegisterForm() {
  const { register: registerUser } = useAuth();
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      await registerUser(values.email, values.password, values.fullName);
      router.push("/chat");
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 w-full max-w-sm">
      <div className="flex flex-col gap-1">
        <label htmlFor="fullName" className="text-sm font-medium">
          Full name
        </label>
        <input
          id="fullName"
          type="text"
          autoComplete="name"
          className="rounded-md border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          {...register("fullName")}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="email" className="text-sm font-medium">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          className="rounded-md border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          {...register("email")}
        />
        {errors.email && <p className="text-sm text-red-500">{errors.email.message}</p>}
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="password" className="text-sm font-medium">
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete="new-password"
          className="rounded-md border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          {...register("password")}
        />
        {errors.password && <p className="text-sm text-red-500">{errors.password.message}</p>}
      </div>

      {serverError && <p className="text-sm text-red-500">{serverError}</p>}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md bg-blue-600 text-white text-sm font-medium py-2 disabled:opacity-50"
      >
        {isSubmitting ? "Creating account..." : "Create account"}
      </button>

      <p className="text-sm text-center text-black/60 dark:text-white/60">
        Already have an account?{" "}
        <Link href="/login" className="text-blue-600 dark:text-blue-400 underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
