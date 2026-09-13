'use client';
import { KnowledgePanel } from '@/components/doctor/KnowledgePanel';
import { AssignmentPanel } from '@/components/doctor/AssignmentPanel';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Activity, ArrowLeft, ShieldCheck, Users } from 'lucide-react';
import {
  type AdminAudit,
  type AdminOntology,
  type AdminUser,
  getAdminAudits,
  getAdminOntology,
  getAdminUsers,
  getCurrentUser,
  saveAdminOntologyRule,
  updateAdminUserRole,
} from '@/services/api';

const roles: AdminUser['role'][] = ['PATIENT', 'DOCTOR', 'ADMIN'];

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [audit, setAudit] = useState<AdminAudit[]>([]);
  const [ontology, setOntology] = useState<AdminOntology | null>(null);
  const [concept, setConcept] = useState('');
  const [ruleJson, setRuleJson] = useState('{"synonyms": [], "required": []}');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    const current = await getCurrentUser();
    if (current.role !== 'ADMIN') throw new Error('Administrator access is required.');
    const [userRows, auditRows, ontologyState] = await Promise.all([getAdminUsers(), getAdminAudits(), getAdminOntology()]);
    setUsers(userRows); setAudit(auditRows); setOntology(ontologyState);
  };

  useEffect(() => { reload().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Could not load administration data.')); }, []);

  const changeRole = async (user: AdminUser, role: AdminUser['role']) => {
    setNotice(null); setError(null);
    try {
      await updateAdminUserRole(user.user_id, role);
      setUsers((rows) => rows.map((row) => row.user_id === user.user_id ? { ...row, role } : row));
      setNotice(`Role updated for ${user.display_name}.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not update this role.'); }
  };

  const saveRule = async (event: React.FormEvent) => {
    event.preventDefault(); setNotice(null); setError(null);
    try {
      const parsed: unknown = JSON.parse(ruleJson);
      if (!concept.trim() || !parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('Enter a concept and a JSON object payload.');
      await saveAdminOntologyRule(`RULE_${concept.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '_')}`, { concept: concept.trim(), payload: parsed as Record<string, unknown>, enabled: true });
      setConcept('');
      await reload();
      setNotice('Ontology rule saved. It is persisted and audited.');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save ontology rule.'); }
  };

  return <main className="min-h-screen bg-slate-50 text-slate-900">
    <header className="bg-slate-900 text-white border-b border-slate-800">
      <div className="max-w-6xl mx-auto px-5 py-5 flex justify-between items-center gap-4">
        <div><p className="text-xs font-bold tracking-[0.2em] text-sky-400">MEDIKIOSK</p><h1 className="text-2xl font-black">Administration</h1></div>
        <Link href="/doctor" className="inline-flex items-center gap-2 rounded-xl px-3 py-2 bg-slate-800 text-sm font-semibold hover:bg-slate-700"><ArrowLeft className="w-4 h-4" /> Clinical queue</Link>
      </div>
    </header>
    <section className="max-w-6xl mx-auto p-5 sm:p-8 space-y-6">
      <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4 flex gap-3"><ShieldCheck className="w-5 h-5 text-sky-700 shrink-0" /><p className="text-sm text-slate-700">Changes here are server-authorized, persisted, and audited. Use synthetic accounts only for the included demo.</p></div>
      {error && <p role="alert" className="rounded-xl p-3 bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</p>}
      {notice && <p role="status" className="rounded-xl p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">{notice}</p>}
      <KnowledgePanel admin />
      <AssignmentPanel users={users} />
      <div className="grid lg:grid-cols-2 gap-6">
        <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden"><div className="p-5 border-b border-slate-100 flex gap-2 items-center"><Users className="w-5 h-5 text-sky-700" /><h2 className="font-bold">Users and roles</h2></div><div className="divide-y divide-slate-100">{users.map((user) => <div key={user.user_id} className="p-4 flex flex-wrap gap-3 justify-between items-center"><div><p className="font-semibold text-sm">{user.display_name}</p><p className="text-xs text-slate-500">{user.email}</p></div><select aria-label={`Role for ${user.display_name}`} className="rounded-lg border border-slate-300 px-2 py-1.5 text-xs font-bold" value={user.role} onChange={(event) => changeRole(user, event.target.value as AdminUser['role'])}>{roles.map((role) => <option key={role}>{role}</option>)}</select></div>)}</div></section>
        <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5"><div className="flex gap-2 items-center"><Activity className="w-5 h-5 text-sky-700" /><h2 className="font-bold">Add ontology rule</h2></div><p className="text-xs text-slate-500 mt-2">Custom rules are stored separately from the built-in safety ontology. Validate clinical governance before enabling a rule in a real deployment.</p><form onSubmit={saveRule} className="space-y-3 mt-4"><label className="block text-xs font-bold">Concept<input required value={concept} onChange={(event) => setConcept(event.target.value)} className="block w-full mt-1 rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="e.g. sore throat" /></label><label className="block text-xs font-bold">Rule payload (JSON)<textarea required value={ruleJson} onChange={(event) => setRuleJson(event.target.value)} className="block w-full h-28 mt-1 font-mono rounded-xl border border-slate-300 px-3 py-2 text-xs" /></label><button className="rounded-xl bg-sky-600 text-white px-4 py-2 text-sm font-bold hover:bg-sky-700" type="submit">Save audited rule</button></form><p className="mt-4 text-xs text-slate-500">Built-in concepts: {ontology ? Object.keys(ontology.built_in).join(', ') : 'Loading…'}</p></section>
      </div>
      <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden"><div className="p-5 border-b border-slate-100"><h2 className="font-bold">Recent audit events</h2></div><div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-3">When</th><th className="p-3">Action</th><th className="p-3">Resource</th></tr></thead><tbody>{audit.slice(0, 50).map((row) => <tr key={row.audit_id} className="border-t border-slate-100"><td className="p-3 text-xs text-slate-500">{new Date(row.created_at).toLocaleString()}</td><td className="p-3 font-semibold">{row.action}</td><td className="p-3 text-slate-600">{row.resource_type}</td></tr>)}</tbody></table></div></section>
    </section>
  </main>;
}
