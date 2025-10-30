import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

import flet as ft
from flet import (
    AppBar,
    Column,
    ElevatedButton,
    IconButton,
    ListView,
    Row,
    Text,
    TextField,
    View,
    alignment,
    border,
    border_radius,
    padding,
    MainAxisAlignment,
    AlertDialog,
    ProgressRing,
    Card,
    Dropdown,
    TextButton,
)

from core.models import Status, Container
from core.services import ProjectService
from infrastructure.config import ConfigManager
from infrastructure.filesystem import FileRepository


def launch_ui(service_instance: ProjectService, root_path: Optional[Path]):
    def main(page: ft.Page):
        page.title = "Config Wizard"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.bgcolor = "grey_100"
        page.padding = 20
        page.window_width = 1200
        page.window_height = 800
        page.window_resizable = True

        # Global file_repo for validation
        file_repo = FileRepository()

        def route_change(e):
            # Dynamically load current root_path on every route change
            current_root = ConfigManager.load_root_path()

            page.views.clear()

            # Setup view (for initial config or re-setup)
            def build_setup_view():
                path_field = TextField(
                    label="Root Path",
                    hint_text="Enter the root directory path for projects (e.g., /home/user/projects)",
                    width=500,
                )

                def validate_path_click(event):
                    if not path_field.value or not path_field.value.strip():
                        snack = ft.SnackBar(content=ft.Text("Please enter a path."))
                        page.snack_bar = snack
                        page.update()
                        return
                    candidate_path = Path(path_field.value.strip())
                    if file_repo.validate_root_path(candidate_path):
                        ConfigManager.save_root_path(candidate_path)
                        snack = ft.SnackBar(content=ft.Text(f"Root path '{candidate_path}' set successfully!"))
                        page.snack_bar = snack
                        page.update()
                        page.go("/")  # Navigate to main; next route_change will load the new path
                    else:
                        snack = ft.SnackBar(
                            content=ft.Text("Invalid path: Must exist or be creatable, and writable."),
                            bgcolor="red",
                        )
                        page.snack_bar = snack
                        page.update()

                validate_button = ElevatedButton(
                    "Validate & Save",
                    on_click=validate_path_click,
                    style=ft.ButtonStyle(
                        bgcolor="green",
                        color="white",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                )

                setup_container = ft.Container(
                    content=ft.Column(
                        [
                            Text("Welcome! Set Root Path", size=24, weight=ft.FontWeight.BOLD),
                            Text("This is where your project directories will be stored.", size=14, color="grey_600"),
                            path_field,
                            validate_button,
                        ],
                        horizontal_alignment=alignment.center,
                        spacing=20,
                    ),
                    padding=padding.all(40),
                    alignment=alignment.center,
                )

                return View(
                    "/setup",
                    [
                        AppBar(title=Text("Setup Root Path"), bgcolor="on_surface_variant"),
                        setup_container,
                    ],
                )

            # Main view for listing projects (only if current_root set) - Slimmed: No controls, add Open button
            def build_project_list_view():
                if not current_root:
                    # Fallback: redirect to setup
                    page.go("/setup")
                    return None
                projects = service_instance.list_projects(current_root)
                projects.sort(key=lambda p: p.name)  # New: Sort by name
                project_list = ListView(
                    spacing=10,
                    padding=padding.all(20),
                    expand=True,
                )
                if not projects:
                    empty_state = ft.Container(
                        content=Text(
                            "No projects yet. Create one to get started!",
                            size=16,
                            text_align=ft.TextAlign.CENTER,
                            color="grey_600",
                        ),
                        alignment=alignment.center,
                        padding=padding.all(50),
                        expand=True,
                    )
                    project_list.controls.append(empty_state)
                else:
                    for proj in projects:
                        status_str = str(proj.status)
                        status_color = "green" if proj.status == Status.RUNNING else "grey" if proj.status == Status.NOT_CREATED else "red"
                        status_icon = "check_circle" if proj.status == Status.RUNNING else "radio_button_unchecked" if proj.status == Status.NOT_CREATED else "pause_circle"

                        # Sub-bullets for containers
                        containers_col = Column(spacing=5)
                        for cont in proj.containers:
                            cont_status = proj.container_statuses.get(cont.name, Status.NOT_CREATED)
                            cont_status_str = str(cont_status)
                            cont_status_color = "green" if cont_status == Status.RUNNING else "grey" if cont_status == Status.NOT_CREATED else "red"
                            cont_status_icon = "check_circle" if cont_status == Status.RUNNING else "radio_button_unchecked" if cont_status == Status.NOT_CREATED else "pause_circle"
                            containers_col.controls.append(
                                Row(
                                    [
                                        Row(
                                            [
                                                Text("•", size=14),
                                                Text(f"{cont.name}", size=14, weight=ft.FontWeight.W_500),
                                                Text(f"({cont.image})", size=12, color="grey_600"),
                                            ],
                                            alignment=MainAxisAlignment.START,
                                        ),
                                        IconButton(
                                            icon=cont_status_icon,
                                            icon_color=cont_status_color,
                                            tooltip=cont_status_str,
                                            icon_size=16,
                                        ),
                                    ],
                                    alignment=MainAxisAlignment.SPACE_BETWEEN,
                                )
                            )
                        
                        # Slim header: Name + status icon + Open button + Delete button
                        def open_detail_click(event, project=proj):
                            page.go(f"/detail/{project.name}")

                        # New: Delete handler with closure
                        def make_delete_click(project):
                            def delete_click(e):
                                def confirm():
                                    page.close(dialog)
                                    try:
                                        service_instance.delete_project(project)
                                        page.snack_bar = ft.SnackBar(content=ft.Text("Deleted successfully"))
                                        page.snack_bar.open = True
                                        page.update()
                                        page.go("/")
                                    except Exception as ex:
                                        page.snack_bar = ft.SnackBar(content=ft.Text(f"Delete failed: {str(ex)}"), bgcolor=ft.Colors.RED)
                                        page.snack_bar.open = True
                                        page.update()

                                dialog = AlertDialog(
                                    modal=True,
                                    title=Text("Confirm Delete"),
                                    content=Text(f"Delete project '{project.name}'? This cannot be undone."),
                                    actions=[
                                        TextButton("Yes", on_click=lambda _: confirm()),
                                        TextButton("No", on_click=lambda _: page.close(dialog)),
                                    ],
                                    actions_alignment=MainAxisAlignment.END,
                                )
                                page.dialog = dialog
                                page.open(dialog)
                                page.update()
                            return delete_click

                        project_container = ft.Container(
                            content=ft.Column(
                                [
                                    Row(
                                        [
                                            Text(proj.name, size=18, weight=ft.FontWeight.BOLD),
                                            IconButton(
                                                icon=status_icon,
                                                icon_color=status_color,
                                                tooltip=status_str,
                                            ),
                                            IconButton(
                                                icon="open_in_new",
                                                icon_color="blue",
                                                on_click=open_detail_click,
                                                tooltip="Open Detail",
                                            ),
                                            IconButton(
                                                icon="delete",
                                                icon_color="red",
                                                on_click=make_delete_click(proj),
                                                tooltip="Delete Project",
                                            ),
                                        ],
                                        alignment=alignment.center,
                                        expand=True
                                    ),
                                    Text(f"Path: {proj.path}", size=12, color="grey_700"),
                                    Text("Containers:", size=14, weight=ft.FontWeight.W_600, color="grey_800"),
                                    containers_col,
                                ],
                                spacing=10,
                            ),
                            padding=padding.all(15),
                            bgcolor="white",
                            border=border.all(1, "grey_300"),
                            border_radius=border_radius.all(8),
                            ink=True,
                        )
                        project_list.controls.append(project_container)

                # Add create button
                create_button = ElevatedButton(
                    "Create New Project",
                    on_click=lambda event: page.go("/create"),
                    style=ft.ButtonStyle(
                        bgcolor="blue",
                        color="white",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                )

                # Add setup button for re-config
                setup_button = ElevatedButton(
                    "Change Root Path",
                    on_click=lambda event: page.go("/setup"),
                    style=ft.ButtonStyle(
                        bgcolor="grey",
                        color="white",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                )

                return View(
                    "/",
                    [
                        AppBar(
                            title=Text("Projects"), 
                            bgcolor="on_surface_variant",
                            actions=[  # New: Refresh button
                                IconButton(ft.Icons.REFRESH, on_click=lambda e: page.go("/"))
                            ]
                        ),
                        Row([create_button, setup_button], alignment=MainAxisAlignment.SPACE_BETWEEN),
                        project_list,
                    ],
                )

            # Shared helper for building container card
            def build_container_card(container_fields, containers_list, prefill_cont=None):
                name_field = TextField(label="Container Name", width=200, value=prefill_cont.name if prefill_cont else "")
                image_field = TextField(label="Image", hint_text="e.g., nginx:latest", width=200, value=prefill_cont.image if prefill_cont else "")
                ports_field = TextField(label="Ports (host:container, comma-sep)", hint_text="e.g., 8080:80,3000:3000", width=300, value=",".join(f"{h}:{c}" for h, c in (prefill_cont.ports.items() if prefill_cont else {})))
                volumes_field = TextField(label="Volumes (host:container, comma-sep)", hint_text="e.g., /data:/app,/logs:/var/log", width=300, value=",".join(f"{h}:{c}" for h, c in (prefill_cont.volumes.items() if prefill_cont else {})))
                env_field = TextField(label="Env Vars (KEY=value, comma-sep)", hint_text="e.g., DB_HOST=localhost,NODE_ENV=prod", width=300, value=",".join(f"{k}={v}" for k, v in (prefill_cont.env.items() if prefill_cont else {})))
                depends_field = TextField(label="Depends On (names, comma-sep)", hint_text="e.g., db,redis", width=300, value=",".join(prefill_cont.depends_on if prefill_cont else []))

                # Fixed: Use Dropdown with DropdownOption (replaces TextField workaround)
                restart_dropdown = Dropdown(
                    label="Restart Policy",
                    options=[
                        ft.DropdownOption("no"),
                        ft.DropdownOption("on-failure"),
                        ft.DropdownOption("always"),
                        ft.DropdownOption("unless-stopped"),
                    ],
                    value=prefill_cont.restart_policy if prefill_cont else "unless-stopped",
                    width=200,
                )

                fields_dict = {
                    'name': name_field,
                    'image': image_field,
                    'ports': ports_field,
                    'volumes': volumes_field,
                    'env': env_field,
                    'depends_on': depends_field,
                    'restart': restart_dropdown,  # Updated key
                }

                remove_btn = IconButton(icon="delete")

                # Fixed: Wrap Column in Container for padding (Column doesn't support it directly)
                card = Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                Row([name_field, image_field], alignment=MainAxisAlignment.START),
                                Row([ports_field, volumes_field], alignment=MainAxisAlignment.START),
                                Row([env_field, depends_field], alignment=MainAxisAlignment.START),
                                Row([restart_dropdown, remove_btn], alignment=MainAxisAlignment.SPACE_BETWEEN),  # Updated
                            ],
                            spacing=10,
                        ),
                        padding=padding.all(10),
                    ),
                    elevation=2,
                )

                # Set on_click after card is defined
                remove_btn.on_click = lambda e: (containers_list.controls.remove(card), container_fields.remove(fields_dict), containers_list.update())

                container_fields.append(fields_dict)
                return card

            # Create view with multistep form
            def build_create_view():
                if not current_root:
                    page.go("/setup")
                    return None

                # Step 1: Project name
                name_field = TextField(
                    label="Project Name",
                    hint_text="Enter a unique project name",
                    width=300,
                )

                containers_list = ListView(expand=1, spacing=10)
                container_fields = []  # List of dicts for fields

                def add_container_click(e):
                    card = build_container_card(container_fields, containers_list)
                    containers_list.controls.append(card)
                    containers_list.update()

                add_cont_btn = ElevatedButton("Add Container", on_click=add_container_click)

                freeform_section = Column(
                    [
                        Text("Containers:", size=16, weight=ft.FontWeight.W_600),
                        add_cont_btn,
                        containers_list,
                    ],
                    visible=True,
                    expand=True,
                )

                def create_project_click(event):
                    if not name_field.value or not name_field.value.strip():
                        page.snack_bar = ft.SnackBar(content=ft.Text("Please enter a project name."))
                        page.update()
                        return

                    parsed_containers = []
                    for fields in container_fields:
                        cname = fields['name'].value.strip()
                        if not cname:
                            continue
                        cimage = fields['image'].value.strip() or "nginx:latest"
                        ports = {}
                        for p in (fields['ports'].value or "").split(","):
                            p = p.strip()
                            if ":" in p:
                                h, c = p.split(":", 1)
                                ports[h.strip()] = c.strip()
                        volumes = {}
                        for v in (fields['volumes'].value or "").split(","):
                            v = v.strip()
                            if ":" in v:
                                h, c = v.split(":", 1)
                                volumes[h.strip()] = c.strip()
                        env = {}
                        for ev in (fields['env'].value or "").split(","):
                            ev = ev.strip()
                            if "=" in ev:
                                k, val = ev.split("=", 1)
                                env[k.strip()] = val.strip()
                        depends_on = [d.strip() for d in (fields['depends_on'].value or "").split(",") if d.strip()]
                        restart = fields['restart'].value or "unless-stopped"
                        parsed_containers.append(Container(cname, cimage, ports, volumes, env, depends_on, restart))

                    try:
                        new_project = service_instance.create_project(
                            name_field.value.strip(),
                            current_root,
                            parsed_containers,
                        )
                        name_field.value = ""

                        container_fields.clear()
                        containers_list.controls.clear()
                        containers_list.update()
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"Project '{new_project.name}' created successfully!"))
                        page.update()
                        page.go("/")
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"Error creating project: {str(ex)}"), bgcolor="red")
                        page.update()

                create_button = ElevatedButton(
                    "Create Project",
                    on_click=create_project_click,
                    style=ft.ButtonStyle(
                        bgcolor="green",
                        color="white",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                )

                cancel_button = ElevatedButton(
                    "Cancel",
                    on_click=lambda event: page.go("/"),
                    style=ft.ButtonStyle(
                        bgcolor="grey",
                        color="white",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                )

                form_scroll = Column(
                    [
                        Text("Create New Project", size=24, weight=ft.FontWeight.BOLD),
                        name_field,
                        freeform_section,
                        Row([create_button, cancel_button], alignment=alignment.center),
                    ],
                    horizontal_alignment=alignment.center,
                    spacing=20,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                )

                form_container = ft.Container(
                    content=form_scroll,
                    padding=padding.all(40),
                    alignment=alignment.center,
                    expand=True,
                )

                return View(
                    "/create",
                    [
                        AppBar(title=Text("Create Project"), bgcolor="on_surface_variant"),
                        form_container,
                    ],
                )

            # Update view (Enhanced: Similar to create, pre-fill cards)
            def build_update_view():
                if not current_root:
                    page.go("/setup")
                    return None

                current_route = page.route
                project_name = unquote(current_route.split("/update/")[1]) if "/update/" in current_route else ""
                if not project_name:
                    snack = ft.SnackBar(content=ft.Text("Invalid project name."), bgcolor="red")
                    page.snack_bar = snack
                    page.update()
                    page.go("/")
                    return None

                # New: Load via get_project
                project_to_update = service_instance.get_project(current_root, project_name)
                if not project_to_update:
                    snack = ft.SnackBar(content=ft.Text(f"Project '{project_name}' not found."), bgcolor="red")
                    page.snack_bar = snack
                    page.update()
                    page.go("/")
                    return None

                name_field = TextField(
                    label="Project Name",
                    value=project_to_update.name,  # Pre-fill
                    width=300,
                )

                # Containers: Pre-populate cards
                containers_list = ListView(expand=1, spacing=10)
                container_fields = []

                def add_container_click(e):
                    card = build_container_card(container_fields, containers_list)
                    containers_list.controls.append(card)
                    containers_list.update()

                # Pre-fill existing containers
                for cont in project_to_update.containers:
                    card = build_container_card(container_fields, containers_list, prefill_cont=cont)
                    containers_list.controls.append(card)

                add_cont_btn = ElevatedButton("Add Container", on_click=add_container_click)

                def update_project_click(event):
                    new_name = name_field.value.strip() if name_field.value else ""
                    if not new_name:
                        page.snack_bar = ft.SnackBar(content=ft.Text("Please enter a project name."))
                        page.update()
                        return
                    if new_name != project_to_update.name:
                        # Check uniqueness
                        existing = service_instance.get_project(current_root, new_name)
                        if existing and existing != project_to_update:
                            page.snack_bar = ft.SnackBar(content=ft.Text("Name already exists."), bgcolor="red")
                            page.update()
                            return

                    # New: Handle rename if name changed
                    old_path = project_to_update.path
                    if new_name != project_to_update.name:
                        new_path = current_root / new_name
                        try:
                            shutil.move(str(old_path), str(new_path))
                            project_to_update.path = new_path
                        except Exception as rename_ex:
                            page.snack_bar = ft.SnackBar(content=ft.Text(f"Rename failed: {str(rename_ex)}"), bgcolor="red")
                            page.update()
                            return

                    project_to_update.name = new_name

                    # Parse containers (enhanced)
                    parsed_containers = []
                    for fields in container_fields:
                        cname = fields['name'].value.strip()
                        if not cname:
                            continue
                        cimage = fields['image'].value.strip() or "nginx:latest"
                        ports = {}
                        for p in (fields['ports'].value or "").split(","):
                            p = p.strip()
                            if ":" in p:
                                h, c = p.split(":", 1)
                                ports[h.strip()] = c.strip()
                        volumes = {}
                        for v in (fields['volumes'].value or "").split(","):
                            v = v.strip()
                            if ":" in v:
                                h, c = v.split(":", 1)
                                volumes[h.strip()] = c.strip()
                        env = {}
                        for ev in (fields['env'].value or "").split(","):
                            ev = ev.strip()
                            if "=" in ev:
                                k, val = ev.split("=", 1)
                                env[k.strip()] = val.strip()
                        depends_on = [d.strip() for d in (fields['depends_on'].value or "").split(",") if d.strip()]
                        restart = fields['restart'].value or "unless-stopped"
                        parsed_containers.append(Container(cname, cimage, ports, volumes, env, depends_on, restart))

                    project_to_update.containers = parsed_containers

                    try:
                        service_instance.update_project(project_to_update)
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"Project '{project_to_update.name}' updated successfully!"))
                        page.update()
                        page.go("/")  # Navigate back to projects list
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"Error updating project: {str(ex)}"), bgcolor="red")
                        page.update()

                update_button = ElevatedButton(
                    "Update Project",
                    on_click=update_project_click,
                    style=ft.ButtonStyle(
                        bgcolor="orange",
                        color="white",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                )

                cancel_button = ElevatedButton(
                    "Cancel",
                    on_click=lambda event: page.go("/"),
                    style=ft.ButtonStyle(
                        bgcolor="grey",
                        color="white",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                )

                form_scroll = Column(
                    [
                        Text("Update Project", size=24, weight=ft.FontWeight.BOLD),
                        name_field,
                        Text("Containers:", size=16, weight=ft.FontWeight.W_600),
                        add_cont_btn,
                        containers_list,
                        Row([update_button, cancel_button], alignment=alignment.center),
                    ],
                    horizontal_alignment=alignment.center,
                    spacing=20,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                )

                form_container = ft.Container(
                    content=form_scroll,
                    padding=padding.all(40),
                    alignment=alignment.center,
                    expand=True,
                )

                return View(
                    f"/update/{project_name}",
                    [
                        AppBar(title=Text(f"Update {project_name}"), bgcolor="on_surface_variant"),
                        form_container,
                    ],
                )

            def build_detail_view():
                if not current_root:
                    page.go("/setup")
                    return None
                current_route = page.route
                project_name = unquote(current_route.split("/detail/")[1]) if "/detail/" in current_route else ""
                if not project_name:
                    snack = ft.SnackBar(content=ft.Text("Invalid project name."), bgcolor="red")
                    page.snack_bar = snack
                    page.update()
                    page.go("/")
                    return None

                # Load via get_project
                project = service_instance.get_project(current_root, project_name)
                if not project:
                    snack = ft.SnackBar(content=ft.Text(f"Project '{project_name}' not found."), bgcolor="red")
                    page.snack_bar = snack
                    page.update()
                    page.go("/")
                    return None

                status_str = str(project.status)
                status_color = "green" if project.status == Status.RUNNING else "grey" if project.status == Status.NOT_CREATED else "red"
                status_icon = "check_circle" if project.status == Status.RUNNING else "radio_button_unchecked" if project.status == Status.NOT_CREATED else "pause_circle"

                # Enhanced containers section with more details
                containers_list = ListView(spacing=5)
                for cont in project.containers:
                    cont_status = project.container_statuses.get(cont.name, Status.NOT_CREATED)
                    cont_status_str = str(cont_status)
                    cont_status_color = "green" if cont_status == Status.RUNNING else "grey" if cont_status == Status.NOT_CREATED else "red"
                    cont_status_icon = "check_circle" if cont_status == Status.RUNNING else "radio_button_unchecked" if cont_status == Status.NOT_CREATED else "pause_circle"
                    ports_str = ", ".join(f"{h}:{c}" for h, c in cont.ports.items()) or "None"
                    volumes_str = ", ".join(f"{h}:{c}" for h, c in cont.volumes.items()) or "None"
                    env_str = ", ".join(f"{k}={v}" for k, v in cont.env.items()) or "None"
                    depends_str = ", ".join(cont.depends_on) or "None"
                    containers_list.controls.append(
                        Column(
                            [
                                Row(
                                    [
                                        Text(f"{cont.name}: {cont.image}", weight=ft.FontWeight.W_500),
                                        IconButton(icon=cont_status_icon, icon_color=cont_status_color, tooltip=cont_status_str, icon_size=16),
                                    ]
                                ),
                                Text(f"Ports: {ports_str}", size=12, color="grey_600"),
                                Text(f"Volumes: {volumes_str}", size=12, color="grey_600"),
                                Text(f"Env: {env_str}", size=12, color="grey_600"),
                                Text(f"Depends On: {depends_str}", size=12, color="grey_600"),
                                Text(f"Restart: {cont.restart_policy}", size=12, color="grey_600"),
                            ],
                            spacing=2,
                        )
                    )

                # Actions: Start/Stop (removed Delete) with handlers
                def start_project_click(e):
                    progress_ring = ProgressRing(visible=True, width=20, height=20)
                    page.overlay.append(progress_ring)
                    page.update()
                    try:
                        output = service_instance.start_project(project)
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"Started: {output or 'Success'}"))
                        page.snack_bar.open = True
                        page.update()
                        # Fixed: Refresh current detail view to update status
                        page.go(f"/detail/{project.name}")
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"Start failed: {str(ex)}"), bgcolor=ft.Colors.RED)
                        page.snack_bar.open = True
                        page.update()
                    finally:
                        page.overlay.remove(progress_ring)
                        page.update()

                def stop_project_click(e):
                    progress_ring = ProgressRing(visible=True, width=20, height=20)
                    page.overlay.append(progress_ring)
                    page.update()
                    try:
                        output = service_instance.stop_project(project)
                        msg = f"Stopped: {output}" if output else "Project stopped."
                        page.snack_bar = ft.SnackBar(content=ft.Text(msg))
                        page.snack_bar.open = True
                        page.update()
                        # Fixed: Refresh current detail view to update status
                        page.go(f"/detail/{project.name}")
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"Stop failed: {str(ex)}"), bgcolor=ft.Colors.RED)
                        page.snack_bar.open = True
                        page.update()
                    finally:
                        page.overlay.remove(progress_ring)
                        page.update()

                actions_row = Row(
                    [
                        ElevatedButton("Start", icon=ft.Icons.PLAY_ARROW, style=ft.ButtonStyle(color="green"), on_click=start_project_click, disabled=project.status == Status.RUNNING),
                        ElevatedButton("Stop", icon=ft.Icons.STOP, style=ft.ButtonStyle(color="red"), on_click=stop_project_click, disabled=project.status != Status.RUNNING),
                        ElevatedButton("Back to List", on_click=lambda _: page.go("/")),
                    ],
                    alignment=MainAxisAlignment.SPACE_AROUND,
                    expand=True,
                )

                # New: Scrollable detail content (similar to create/update)
                detail_scroll = Column(
                    [
                        Text(f"Project: {project.name}", size=24, weight=ft.FontWeight.BOLD),
                        Row(
                            [
                                ft.Icon(status_icon, color=status_color, size=32),  # Fixed: ft.Icon
                                Text(f"Status: {status_str.upper()}", size=18),
                            ],
                            alignment=MainAxisAlignment.START,
                        ),
                        Text(f"Path: {project.path}", size=14, color="grey_700"),
                        Text("Containers:", size=16, weight=ft.FontWeight.W_600),
                        containers_list,
                        actions_row,
                    ],
                    horizontal_alignment=alignment.center,
                    spacing=20,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                )

                detail_container = ft.Container(
                    content=detail_scroll,
                    padding=padding.all(40),
                    alignment=alignment.center,
                )

                return View(
                    f"/detail/{project_name}",
                    [
                        AppBar(
                            title=Text(f"Detail: {project_name}"), 
                            bgcolor="on_surface_variant",
                            actions=[IconButton("edit", on_click=lambda _: page.go(f"/update/{project_name}"), tooltip="Edit")],  # Quick edit
                        ),
                        detail_container,
                    ],
                )

            # Append views based on route
            current_route = page.route
            if current_route == "/setup" or not current_root:
                setup_view = build_setup_view()
                page.views.append(setup_view)
            else:
                main_view = build_project_list_view()
                if main_view:
                    page.views.append(main_view)
                if current_route == "/create":
                    create_view = build_create_view()
                    if create_view:
                        page.views.append(create_view)
                elif current_route.startswith("/update/"):
                    update_view = build_update_view()
                    if update_view:
                        page.views.append(update_view)
                elif current_route.startswith("/detail/"):
                    detail_view = build_detail_view()
                    if detail_view:
                        page.views.append(detail_view)

            # Update the current view
            page.update()

        # Handle route changes
        page.on_route_change = route_change

        # Initial route: setup if no initial root_path, else main
        initial_route = "/setup" if not root_path else "/"
        page.go(initial_route)

    ft.app(main)
