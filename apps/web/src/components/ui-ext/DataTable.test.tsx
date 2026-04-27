import { fireEvent, render, screen } from "@testing-library/react";
import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "./DataTable";

interface Row {
  article: string;
  name: string;
}

const columns: ColumnDef<Row>[] = [
  { accessorKey: "article", header: "Артикул" },
  { accessorKey: "name", header: "Товар" },
];

describe("DataTable", () => {
  it("keeps client-side pagination state when moving between pages", () => {
    render(
      <DataTable
        data={[
          { article: "A-001", name: "Первый" },
          { article: "A-002", name: "Второй" },
          { article: "A-003", name: "Третий" },
          { article: "A-004", name: "Четвёртый" },
          { article: "A-005", name: "Пятый" },
        ]}
        columns={columns}
        initialPageSize={2}
      />,
    );

    expect(screen.getByText("1–2 из 5")).toBeInTheDocument();
    expect(screen.getByText("Первый")).toBeInTheDocument();
    expect(screen.queryByText("Третий")).not.toBeInTheDocument();

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[buttons.length - 1]!);

    expect(screen.getByText("3–4 из 5")).toBeInTheDocument();
    expect(screen.getByText("Третий")).toBeInTheDocument();
    expect(screen.queryByText("Первый")).not.toBeInTheDocument();
  });
});
