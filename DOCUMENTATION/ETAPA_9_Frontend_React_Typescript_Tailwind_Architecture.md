# ETAPA 9 — FRONTEND SPA (REACT + TYPESCRIPT + TAILWINDCSS)

# 1. OBJETIVO

O frontend será uma SPA SaaS moderna responsável por:

* Autenticação JWT
* Dashboards por role
* Gestão clínica
* Navegação centralizada
* Integração com API Gateway
* UX responsiva
* Estado global
* Loading/error handling
* Visualização médica

---

# 2. STACK

| Tecnologia      | Uso          |
| --------------- | ------------ |
| React           | UI           |
| TypeScript      | Type safety  |
| TailwindCSS     | Styling      |
| React Router    | Routing      |
| Axios           | HTTP client  |
| React Hook Form | Forms        |
| Zod             | Validation   |
| Context API     | Global state |
| Lucide React    | Icons        |

---

# 3. ESTRUTURA GLOBAL

```text
frontend/
├── public/
│
├── src/
│
│   ├── app/
│   │   ├── router.tsx
│   │   └── providers.tsx
│   │
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Spinner.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Badge.tsx
│   │   │
│   │   ├── charts/
│   │   │   ├── PatientsChart.tsx
│   │   │   ├── ReportsChart.tsx
│   │   │   └── AnalyticsChart.tsx
│   │   │
│   │   ├── forms/
│   │   │   ├── LoginForm.tsx
│   │   │   ├── PatientForm.tsx
│   │   │   └── MedicalRecordForm.tsx
│   │   │
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Navbar.tsx
│   │   │   ├── PageContainer.tsx
│   │   │   └── ProtectedLayout.tsx
│   │   │
│   │   
│   ├── contexts/
│   │   ├── AuthContext.tsx
│   │   ├── ThemeContext.tsx
│   │   └── NotificationContext.tsx
│   │
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useApi.ts
│   │   ├── usePatients.ts
│   │   ├── useMedicalRecords.ts
│   │   └── useReports.ts
│   │
│   ├── layouts/
│   │   ├── DashboardLayout.tsx
│   │   └── AuthLayout.tsx
│   │
│   ├── pages/
│   │   ├── auth/
│   │   │   └── LoginPage.tsx
│   │   │
│   │   ├── dashboard/
│   │   │   └── DashboardPage.tsx
│   │   │
│   │   ├── patients/
│   │   │   ├── PatientListPage.tsx
│   │   │   └── PatientDetailsPage.tsx
│   │   │
│   │   ├── clinical/
│   │   │   └── MedicalRecordsPage.tsx
│   │   │
│   │   ├── reports/
│   │   │   
│   │   
│   ├── services/
│   │   ├── api.ts
│   │   ├── auth.service.ts
│   │   
│   
│   ├── styles/
│   │   
│   
│   └── App.tsx
│   
├── tailwind.config.ts
├── tsconfig.json
├── vite.config.ts
└── package.json
```

---