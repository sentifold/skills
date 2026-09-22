# Онбординг Sentifold skills

Цель: `/orchestrate` в Claude Code и `$orchestrate` в Codex работают в проекте
участника, включая его проверки и независимое ревью, без checkout gamejam.

1. **Доступ и версия.** Участник проверяет доступ к приватному `sentifold/skills`,
   Python 3.11+, Bash и нужному CLI. Использует проверенный commit, для gamejam —
   `.agents/shared-skills.lock.json`. Авторизацию сохраняет у себя.
2. **Источники.** Запускает `install.py plan --runtime both` (или один runtime),
   читает реальные source/destination paths. При наличии dotfiles передаёт
   владение только общими пакетами по README. Папки с личными правками сохраняет;
   `--adopt NAME` предназначен для явно выбранных ссылок.
3. **Установка.** Запускает `apply`, затем `doctor` с теми же home/runtime roots.
   `doctor` сам проверяет старые дубликаты в `~/.codex/skills` и, для Codex,
   `features.multi_agent` / `agents.max_depth` в `config.toml`; копии общих
   пакетов внутри проекта проверяет тест проекта (в gamejam —
   `Scripts/tests/test_shared_skills_setup.py`). Состояние установщика лежит в
   `~/.local/share/sentifold-skills-state/` (receipt и, на время `apply`,
   журнал); прерванный `apply` восстанавливается следующим `plan`/`apply`.
   Установщик не меняет model, auth, MCP или настройки approvals.
4. **Новый сеанс.** Открывает свой проект и проверяет обнаружение orchestrate и
   review-agent. До реализации задачи агент должен назвать правильный проект,
   базу и проверки. Для пилота Михаила: sleash, main, make check; дополнительные
   targets и бот — только по актуальному контракту его ветки.
5. **Проверка CLI.** Выбирает доступную модель явно. Helper пишет фактический CLI
   path/version и run ID. Если PATH-бинарник не поддерживает выбранную модель,
   проверяет установку; смена бинарника выполняется явно. Для app-поставки
   companion `codex-code-mode-host` должен поставляться с тем же CLI. Модель и
   пользовательский routing wrapper автоматически не заменяются.
6. **Настоящая задача.** Проходит небольшое исправление с проверяемым результатом,
   реальными проектными checks и ревью в обоих runtime, которые использует.
   Отдельно проверяет второй провайдер. Недоступный CLI/auth, ранний финал дочернего
   агента и отсутствие SendMessage должны дать восстановление или честный
   INCOMPLETE, а не зависание и не фиктивное успешное ревью.
7. **Обновление и откат.** Устанавливает новую версию из другого checkout, затем
   возвращает прежнюю через её `install.py apply` (для gamejam —
   `Scripts/setup-shared-skills.py --revision <старый-commit> apply`). Запускает
   обычный dotfiles sync и снова doctor: старые источники не должны вернуть себе
   ссылки; если вернули, `plan` называет запись и действие (восстановить,
   удалить пересозданный legacy-link или повторить `--adopt NAME`).
8. **Обратная связь.** Общий workflow исправляется PR в skills; продуктовые gates —
   PR в проект; настройка машины — в её конфигурации. Не править установленный
   релиз посреди продуктовой задачи.

## Подключение проекта (Connect a project)

Процедура для любого потребителя без checkout gamejam. Все пути ниже — внутри
checkout проекта.

1. **Установить закреплённый релиз по README.** Из checkout `sentifold/skills`
   на проверенном commit: `python3 install.py plan --runtime both`, затем
   `apply` и `doctor` с теми же `--home`/`--runtime`. Проект, у которого есть
   pin-файл (п. 5), вместо этого запускает свой bootstrap.
2. **Создать профиль.** Скопировать `templates/project-workflow.md` из релиза в
   `.agents/project-workflow.md` проекта (папку `.agents/` создать, если её
   нет — у sleash сейчас нет ни `.agents/`, ни `.claude/`, ни `.codex/`) и
   заменить каждый `<placeholder>` фактами этого checkout: база — `develop` у
   gamejam и cloud, `main` у sleash, captain и codex-multi-auth, `master` у
   teamclaude; проверки — у sleash `make check` по `AGENTS.md`, у cloud
   `make check` и для перечисленных там user-facing изменений финальный
   `make e2e`. Ненужный пункт удалить, а не оставлять догадку; профиль не
   импортирует команды другого проекта. Пример заполненного профиля:
   `examples/sleash.project-workflow.md`; эталон с продуктовыми gates —
   `.agents/project-workflow.md` в gamejam.
3. **Codex: разрешить вложенных агентов.** Для топологии review-agent
   (caller → `review-orchestrator` → `review-lens`) в `config.toml` нужны
   `[features] multi_agent = true` и `[agents] max_depth = 2` — в
   пользовательском `~/.codex/config.toml` (его проверяет `doctor`) или в
   проектном `.codex/config.toml` (его `doctor` не читает). Claude Code
   настройки не требует.
4. **Smoke.** Открыть новый сеанс в проекте и запустить `/orchestrate`
   (Claude Code) или `$orchestrate` (Codex) на крошечном изменении документации.
   Ожидаемо: агент читает профиль и называет базу и проверки проекта; для
   runtime smoke записывает `not-applicable:` с причиной; Final Review
   запускает обе ветки провайдеров или честно завершается
   `REVIEW INCOMPLETE` с причиной. Если `## Provider policy` оставлен как
   `ask`, запуск остановится на вопросе о модели — это ожидаемо; ответить
   явно или заполнить раздел моделями.
5. **Pin-файл (по желанию).** Проект, которому нужна зафиксированная ревизия,
   повторяет схему gamejam: `.agents/shared-skills.lock.json` с полями
   `version`, `repository`, `revision` (полный commit) и `packages`, плюс
   bootstrap `Scripts/setup-shared-skills.py {plan,apply,doctor,uninstall,run}`
   с `--revision <commit>` и `--cache-dir`, который клонирует релиз в
   `$XDG_CACHE_HOME/sentifold-skills/<revision>` (по умолчанию
   `~/.cache/sentifold-skills/<revision>`), проверяет его и запускает
   `install.py` с `--package` из lock. Остальные проекты могут скопировать эту
   схему или полагаться на установленный релиз.
6. **Обновление и откат.** Новая ревизия: `install.py apply` из нового checkout
   с теми же roots (или PR с новым `revision` в lock и bootstrap `apply`).
   Откат: `install.py apply` из прежнего checkout, для pin-проектов —
   bootstrap `--revision <прежний-commit> apply`. После — `doctor` и smoke из
   п. 4.
7. **Куда идут исправления.** Общий workflow, скрипты, шаблон — PR в
   `sentifold/skills`; база, проверки, executors, пути отчётов проекта — PR в
   его `.agents/project-workflow.md`.

Для пилота записать: участник, проект, runtime и CLI version, skills commit,
команды checks, ссылка на реальную задачу/PR, результат второго провайдера и
update/rollback. Пустые пункты означают непроверенную часть, а не PASS.

Сначала пилот Михаила в sleash и ещё одного участника в gamejam, затем остальные
активные проекты. Эти PR предоставляют комплект и процедуру; они не доказывают,
что вся команда уже установила его. Не отправлять сообщения участникам без
явного поручения пользователя.
