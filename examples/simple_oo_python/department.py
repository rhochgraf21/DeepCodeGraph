from person import Employee


class Department:
    def __init__(self, name):
        self.name = name
        self.employees = []

    def add_employee(self, emp: Employee):
        self.employees.append(emp)

    def list_employees(self):
        for emp in self.employees:
            print(emp.name)
