import Link from 'next/link';

const ROLES = [
  {
    href: '/rw/docs/citizen',
    title: 'Nshaka gutanga ikibazo',
    body: 'Ohereza ikibazo ukoresheje urubuga rusange, hanyuma ukurikirane aho kigeze. Nta konti ukeneye.',
  },
  {
    href: '/rw/docs/staff/field-officer',
    title: 'Nakira ibibazo by’abaturage',
    body: 'Akira ikibazo imbonankubone, kuri telefoni cyangwa kuri SMS, hanyuma ukinjize muri sisitemu.',
  },
  {
    href: '/rw/docs/staff/reviewer',
    title: 'Ngena uwakemura ikibazo kandi nkandika icyemezo',
    body: 'Genzura ibibazo bishya, ubyohereze ku mukozi ubikwiye, wandike icyemezo cyafashwe.',
  },
  {
    href: '/rw/docs/staff/administrator',
    title: 'Nshyiraho kandi nyobora sisitemu',
    body: 'Fungura umushinga, winjizemo uturere, wongeremo abakozi, uhitemo uko ibibazo byoherezwa.',
  },
  {
    href: '/rw/docs/mobile',
    title: 'Nkorera kuri telefoni',
    body: 'Andika ibibazo uri mu kazi ukoresheje porogaramu ya telefoni, waba ufite murandasi cyangwa utayifite.',
  },
];

export default function HomePage() {
  return (
    <main className="flex flex-1 flex-col items-center px-4 py-16">
      <div className="w-full max-w-3xl">
        <h1 className="text-3xl font-bold tracking-tight">
          Uburyo bwo gukoresha eGRM
        </h1>
        <p className="mt-3 text-fd-muted-foreground">
          Uko watanga ikibazo, n&rsquo;uko gikemurwa. Byanditswe ku bantu
          bakoresha sisitemu, atari ku bayubaka.
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
          Ntuzi aho gutangirira? Tangirira ku{' '}
          <Link href="/rw/docs" className="font-medium underline">
            ntangiriro y&rsquo;iyi mfashanyigisho
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
