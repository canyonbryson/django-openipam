import React, { useState } from "react";
import { useDomainsTable } from "./useDomainsTable";
import { Table } from "../../components/table";
import { AddDomainModule } from "./addDomainModule";
export const Domains = () => {
  const [showAddDomain, setShowAddDomain] = useState(false);
  const table = useDomainsTable({
    setShowAddDomain: setShowAddDomain,
  });
  return (
    <div className="m-8 flex flex-col gap-2 items-center justify-center text-white">
      <h1 className="text-4xl">Domains</h1>
      <h4>Here is some info and some options</h4>
      <div className="flex flex-col gap-4 m-8">
        <Table table={table.table} loading={false} />
      </div>
      <AddDomainModule
        showModule={showAddDomain}
        setShowModule={setShowAddDomain}
      />
    </div>
  );
};