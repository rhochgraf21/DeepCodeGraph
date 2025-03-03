from department import Department
from employee import Employee


class Company:
    def __init__(self, name):
        self.name = name
        self.departments = []

    def add_department(self, dept: Department):
        self.departments.append(dept)

    def hire_employee(self, dept_name, employee: Employee):
        for dept in self.departments:
            if dept.name == dept_name:
                dept.add_employee(employee)
                return
        print("Department not found!")
