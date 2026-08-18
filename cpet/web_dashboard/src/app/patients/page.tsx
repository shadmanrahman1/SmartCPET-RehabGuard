"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Plus, Search, FileText, Loader2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import Link from "next/link"
import { databases, APPWRITE_CONFIG } from "@/lib/appwrite"

interface AppwritePatient {
  $id: string;
  name: string;
  age: number;
  position: string;
  last_test_date: string;
  fitness_status: string;
}

export default function PatientsPage() {
  const [patients, setPatients] = useState<AppwritePatient[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchPatients() {
      try {
        const response = await databases.listDocuments(
          APPWRITE_CONFIG.databaseId,
          APPWRITE_CONFIG.collections.patients
        );
        setPatients(response.documents as unknown as AppwritePatient[]);
      } catch (error) {
        console.error("Failed to fetch patients:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchPatients();
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Patients</h2>
        <Button>
          <Plus className="mr-2 h-4 w-4" /> Add Patient
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input type="search" placeholder="Search patients..." className="pl-8" />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Patients</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin mb-4 text-emerald-500" />
              <p>Loading patient records...</p>
            </div>
          ) : patients.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground border border-dashed border-[var(--border-accent)] rounded-lg">
              <UsersIcon className="h-10 w-10 mb-2 opacity-50" />
              <p className="text-lg font-medium text-foreground">No patients found</p>
              <p className="text-sm">Click &quot;Add Patient&quot; to register a new athlete.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Patient ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Age</TableHead>
                  <TableHead>Position</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Test</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {patients.map((patient) => (
                  <TableRow key={patient.$id}>
                    <TableCell className="font-medium text-muted-foreground">
                      {patient.$id.substring(0, 8)}
                    </TableCell>
                    <TableCell className="font-semibold text-foreground">{patient.name}</TableCell>
                    <TableCell>{patient.age}</TableCell>
                    <TableCell>
                      {patient.position ? (
                        <span className="px-2 py-1 bg-secondary rounded-md text-xs">{patient.position}</span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 rounded-md text-xs font-semibold ${
                        patient.fitness_status === 'Cleared' ? 'bg-[var(--accent-soft)] text-[var(--emerald-color)]' :
                        patient.fitness_status === 'At Risk' ? 'bg-destructive/10 text-[var(--red-color)]' :
                        'bg-muted text-muted-foreground'
                      }`}>
                        {patient.fitness_status || 'Pending'}
                      </span>
                    </TableCell>
                    <TableCell>
                      {patient.last_test_date ? new Date(patient.last_test_date).toLocaleDateString() : 'Never'}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link href={`/analysis/${patient.$id}`} className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors hover:bg-[var(--accent-soft)] hover:text-[var(--color-primary)] h-9 px-3">
                        <FileText className="h-4 w-4 mr-2" />
                        Analysis
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function UsersIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}
