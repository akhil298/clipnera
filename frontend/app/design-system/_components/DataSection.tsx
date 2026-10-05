'use client';

import { useState } from 'react';

import {
  Button,
  CopyField,
  type DataTableColumn,
  DataTable,
  EmptyState,
  Pagination,
  type SortState,
  Sparkline,
  StatCard,
  StatusBadge,
  TimeCode,
} from '@/components/ui';

import { GallerySection, Specimen, State, StateGrid } from './Specimen';

interface Payment {
  id: string;
  customer: string;
  plan: string;
  amount: number;
  status: 'ready' | 'failed' | 'processing';
}

const PAYMENTS: ReadonlyArray<Payment> = [
  { id: 'pay_1042', customer: 'Asha Rao', plan: 'Pro', amount: 1999, status: 'ready' },
  { id: 'pay_1041', customer: 'Vikram Shah', plan: 'Starter', amount: 799, status: 'processing' },
  { id: 'pay_1040', customer: 'Meera Iyer', plan: 'Pro', amount: 1999, status: 'failed' },
  { id: 'pay_1039', customer: 'Dev Patel', plan: 'Credit pack 500', amount: 499, status: 'ready' },
];

const rupees = (n: number) => `₹${n.toLocaleString('en-IN')}`;

const COLUMNS: ReadonlyArray<DataTableColumn<Payment>> = [
  { key: 'customer', header: 'Customer', primary: true, sortable: true, render: (row) => row.customer },
  { key: 'plan', header: 'Plan', render: (row) => row.plan },
  { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
  { key: 'amount', header: 'Amount', numeric: true, sortable: true, render: (row) => rupees(row.amount) },
];

type TableState = 'full' | 'loading' | 'empty';

const MANY: ReadonlyArray<Payment> = Array.from({ length: 500 }, (_, index) => ({
  id: `pay_${2000 + index}`,
  customer: `Customer ${index + 1}`,
  plan: index % 3 === 0 ? 'Pro' : 'Starter',
  amount: index % 3 === 0 ? 1999 : 799,
  status: 'ready',
}));

export function DataSection() {
  const [sort, setSort] = useState<SortState>({ key: 'customer', direction: 'ascending' });
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set(['pay_1040']));
  const [state, setState] = useState<TableState>('full');
  const [page, setPage] = useState(3);

  const rows = [...PAYMENTS].sort((a, b) => {
    const key = sort.key as keyof Payment;
    const order = a[key] < b[key] ? -1 : a[key] > b[key] ? 1 : 0;
    return sort.direction === 'ascending' ? order : -order;
  });

  return (
    <GallerySection id="data" title="Data and figures" intro="Tables, pages, headline numbers and the small read-outs around them.">
      <Specimen title="DataTable" note="Sortable headers (aria-sort), select-all with indeterminate, loading and empty rows. Below md it becomes stacked cards.">
        <div className="mb-4 flex flex-wrap gap-2">
          {(['full', 'loading', 'empty'] as const).map((option) => (
            <Button key={option} size="sm" variant={state === option ? 'primary' : 'secondary'} onClick={() => setState(option)}>
              {option}
            </Button>
          ))}
          <span className="self-center text-cn-caption text-cn-fg-muted">{selected.size} selected</span>
        </div>
        <DataTable
          caption="Payments"
          columns={COLUMNS}
          rows={state === 'full' ? rows : []}
          getRowId={(row) => row.id}
          getRowLabel={(row) => `payment from ${row.customer}`}
          sort={sort}
          onSortChange={setSort}
          selectedIds={selected}
          onSelectionChange={setSelected}
          loading={state === 'loading'}
          empty={<EmptyState size="compact" level={3} title="No payments yet" description="Payments show here as soon as someone subscribes or buys credits." />}
        />
      </Specimen>

      <Specimen title="DataTable, virtualised" note="500 rows; only those in view are in the DOM (from md up). Header stays sticky.">
        <DataTable caption="All payments" columns={COLUMNS} rows={MANY} getRowId={(row) => row.id} virtualize scrollClassName="max-h-80" />
      </Specimen>

      <Specimen title="Pagination" note="Numbers from sm up, 'Page 3 of 12' on phones; cursor mode shows Previous/Next only.">
        <div className="space-y-4">
          <Pagination page={page} pageCount={12} onPageChange={setPage} label="Payments pages" />
          <Pagination page={2} hasNext onPageChange={() => undefined} label="Activity pages" />
        </div>
      </Specimen>

      <Specimen title="StatCard and Sparkline" note="Change carries an arrow and words, not colour alone. No value shows a dash and why, never a made-up number.">
        <StateGrid className="lg:grid-cols-4">
          <State label="with trend" className="w-full">
            <StatCard
              label="Views, last 7 days"
              value="12,480"
              delta={{ value: '+18%', direction: 'up', good: true, period: 'vs last week' }}
              chart={<Sparkline data={[320, 410, 380, 520, 610, 580, 720]} label="Views rising from 320 to 720 over 7 days" />}
              className="w-full"
            />
          </State>
          <State label="accent, falling" className="w-full">
            <StatCard
              label="Credits left"
              value="1,240"
              tone="accent"
              delta={{ value: '−260', direction: 'down', period: 'this week' }}
              chart={<Sparkline data={[1500, 1480, 1420, 1390, 1310, 1260, 1240]} tone="neutral" label="Credits falling from 1,500 to 1,240" />}
              className="w-full"
            />
          </State>
          <State label="no data" className="w-full">
            <StatCard label="Watch time" value={null} emptyText="No views yet" className="w-full" />
          </State>
          <State label="loading" className="w-full">
            <StatCard label="Followers" value="0" loading className="w-full" />
          </State>
        </StateGrid>
      </Specimen>

      <Specimen title="TimeCode and CopyField">
        <StateGrid className="lg:grid-cols-3">
          <State label="timecode">
            <TimeCode seconds={65} />
          </State>
          <State label="current / total">
            <TimeCode seconds={42.4} total={3725} />
          </State>
          <State label="frames, muted">
            <TimeCode seconds={65.5} fps={30} tone="muted" />
          </State>
          <State label="copy field" className="col-span-2 w-full">
            <CopyField label="Share link" value="https://clipnera.com/s/ep12-hook" className="w-full" />
          </State>
          <State label="masked" className="w-full">
            <CopyField ariaLabel="Webhook secret" value="whsec_9f3a7c2b" masked className="w-full" />
          </State>
        </StateGrid>
      </Specimen>
    </GallerySection>
  );
}
