import Link from 'next/link';

const ROLES = [
  {
    href: '/docs/citizen',
    title: 'I want to report a problem',
    body: 'Send a complaint from the public website and check on it later. No account needed.',
  },
  {
    href: '/docs/staff/field-officer',
    title: 'I record complaints from the public',
    body: 'Take a complaint in person, by phone or by SMS and enter it into the system.',
  },
  {
    href: '/docs/staff/reviewer',
    title: 'I assign and resolve complaints',
    body: 'Check new complaints, route them to the right officer, and record the outcome.',
  },
  {
    href: '/docs/staff/administrator',
    title: 'I set up and run the system',
    body: 'Create a project, load regions, add staff, and decide how complaints are routed.',
  },
  {
    href: '/docs/mobile',
    title: 'I work from a phone',
    body: 'Record complaints in the field on the mobile app, with or without signal.',
  },
];

export default function HomePage() {
  return (
    <main className="flex flex-1 flex-col items-center px-4 py-16">
      <div className="w-full max-w-3xl">
        <h1 className="text-3xl font-bold tracking-tight">eGRM User Guide</h1>
        <p className="mt-3 text-fd-muted-foreground">
          How to report a problem, and how it gets resolved. Written for people
          using the system, not for people building it.
        </p>

        <div className="mt-10 grid gap-3 sm:grid-cols-2">
          {ROLES.map((role) => (
            <Link
              key={role.href}
              href={role.href}
              className="rounded-lg border bg-fd-card p-4 transition-colors hover:bg-fd-accent"
            >
              <span className="font-medium">{role.title}</span>
              <span className="mt-1 block text-sm text-fd-muted-foreground">
                {role.body}
              </span>
            </Link>
          ))}
        </div>

        <p className="mt-10 text-sm text-fd-muted-foreground">
          Not sure? Start at the{' '}
          <Link href="/docs" className="font-medium underline">
            beginning of the guide
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
