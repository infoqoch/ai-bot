#!/bin/bash

cd "$(dirname "$0")"

DB_PATH="$(pwd)/.data/bot.db"
SELECTED_TABLE=""

require_sqlite3() {
    if ! command -v sqlite3 > /dev/null 2>&1; then
        echo "sqlite3 command not found."
        exit 1
    fi
}

require_db_file() {
    if [ ! -f "$DB_PATH" ]; then
        echo "DB file not found: $DB_PATH"
        exit 1
    fi
}

list_tables_raw() {
    sqlite3 "$DB_PATH" \
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
}

show_table_list() {
    echo ""
    echo "테이블 목록"
    sqlite3 -header -column "$DB_PATH" \
        "SELECT name AS table_name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
}

select_table() {
    local tables=()
    local table

    SELECTED_TABLE=""

    while IFS= read -r table; do
        if [ -n "$table" ]; then
            tables[${#tables[@]}]="$table"
        fi
    done < <(list_tables_raw)

    if [ "${#tables[@]}" -eq 0 ]; then
        echo "조회 가능한 테이블이 없습니다."
        return 1
    fi

    echo ""
    echo "조회할 테이블을 선택하세요."
    PS3="table> "
    select table in "${tables[@]}" "뒤로가기"; do
        if [ -z "$table" ]; then
            echo "번호를 다시 선택하세요."
            continue
        fi

        if [ "$table" = "뒤로가기" ]; then
            return 1
        fi

        SELECTED_TABLE="$table"
        return 0
    done
}

show_table_rows() {
    local row_count

    row_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM \"$SELECTED_TABLE\";")

    echo ""
    echo "테이블: $SELECTED_TABLE"
    echo "rows  : $row_count"

    if command -v less > /dev/null 2>&1; then
        sqlite3 -cmd ".headers on" -cmd ".mode column" "$DB_PATH" \
            "SELECT * FROM \"$SELECTED_TABLE\";" | less -FXSR
    else
        sqlite3 -cmd ".headers on" -cmd ".mode column" "$DB_PATH" \
            "SELECT * FROM \"$SELECTED_TABLE\";"
    fi
}

open_sql_shell() {
    echo ""
    echo "sqlite3 셸"
    echo "종료: .quit"
    sqlite3 -cmd ".headers on" -cmd ".mode column" "$DB_PATH"
}

main_menu() {
    local choice

    while true; do
        echo ""
        echo "=== SQLite Menu ==="
        echo "DB: $DB_PATH"
        echo "1. 테이블 리스트"
        echo "2. 테이블 선택 -> 테이블 전체 조회"
        echo "3. 쿼리 작성"
        echo "4. 종료"
        printf "선택> "

        if ! read -r choice; then
            echo ""
            exit 0
        fi

        case "$choice" in
          1)
            show_table_list
            ;;
          2)
            if select_table; then
                show_table_rows
            fi
            ;;
          3)
            open_sql_shell
            ;;
          4|q|quit|exit)
            exit 0
            ;;
          *)
            echo "1, 2, 3, 4 중에서 선택하세요."
            ;;
        esac
    done
}

require_sqlite3
require_db_file
main_menu
