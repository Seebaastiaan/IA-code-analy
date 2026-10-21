import { ThemeToggle } from '@/shared/ui'
import { LoginForm } from '../components/LoginForm'
import { LoginHero } from '../components/LoginHero'

export default function LoginPage() {
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <LoginHero />
      <div className="flex items-center justify-center p-6 relative">
        <ThemeToggle className="absolute top-4 right-4" />
        <LoginForm />
      </div>
    </div>
  )
}
