import csv
import io
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from .conf import LogViewerConfigHelper as config
from .utils import LogManager, ASCTIME_REGEX


def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class LogAnalyticsEngine:
    """
    High-performance Log Analytics & Inspection Engine.
    Provides memory-efficient log streaming, payload sanitization,
    KPI calculations, 24-hour traffic histograms, entity lifecycle scanning,
    and payload inspection.
    """

    # In-memory LRU-like cache: { (file_path, mtime): overview_data }
    _overview_cache = {}

    def __init__(self, log_manager=None):
        self.log_manager = log_manager or LogManager()
        self.compiled_entity_patterns = [
            re.compile(p) for p in config.entity_patterns()
        ]

    def get_available_files(self):
        """
        Discovers all log files from logging settings, rotated archives,
        and configured directories.
        """
        discovered = []
        seen_paths = set()
        exclude_patterns = config.exclude_files()

        # 1. From LogManager / settings.LOGGING
        for log_entry in self.log_manager.logs:
            raw_path = log_entry.get('name')
            if not raw_path:
                continue
            abs_path = os.path.abspath(os.fspath(raw_path))
            parent_dir = os.path.dirname(abs_path)
            basename = os.path.basename(abs_path)
            ext = getattr(settings, 'LOG_FILE_EXTENSION', '.log')
            base_prefix = basename[:-len(ext)] if basename.endswith(ext) else basename

            if os.path.isdir(parent_dir):
                try:
                    for fname in os.listdir(parent_dir):
                        full_fpath = os.path.join(parent_dir, fname)
                        if not os.path.isfile(full_fpath):
                            continue
                        # Match current file or rotated files (e.g. app.log, app.log.1, app.log.2023-11-22)
                        if fname == basename or fname.startswith(base_prefix):
                            if full_fpath not in seen_paths:
                                seen_paths.add(full_fpath)
                                discovered.append(self._make_file_info(fname, full_fpath, is_primary=(fname == basename)))
                except OSError:
                    pass

        # 2. From extra search directories
        extra_dirs = config.file_search_directories()
        for d in extra_dirs:
            pdir = os.path.abspath(os.fspath(d))
            if os.path.isdir(pdir):
                try:
                    for fname in os.listdir(pdir):
                        full_fpath = os.path.join(pdir, fname)
                        if os.path.isfile(full_fpath) and full_fpath not in seen_paths:
                            seen_paths.add(full_fpath)
                            discovered.append(self._make_file_info(fname, full_fpath, is_primary=False))
                except OSError:
                    pass

        # Filter exclusions
        filtered = []
        for f in discovered:
            excluded = False
            for pat in exclude_patterns:
                if pat in f['name'] or pat in f['path']:
                    excluded = True
                    break
            if not excluded:
                filtered.append(f)

        # Sort: primary first, then newest modified
        filtered.sort(key=lambda x: (not x['is_primary'], -x['modified_timestamp']))
        return filtered

    def _make_file_info(self, name, full_path, is_primary=False):
        try:
            st = os.stat(full_path)
            size = st.st_size
            mtime = st.st_mtime
        except OSError:
            size = 0
            mtime = 0

        # Try to infer date from filename (e.g. app.log.2023-11-22 or 2023-11-22.log)
        date_match = re.search(r'(\d{4}[-_]\d{2}[-_]\d{2})', name)
        inferred_date = date_match.group(1).replace('_', '-') if date_match else None
        if not inferred_date and mtime:
            inferred_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

        return {
            'name': name,
            'path': full_path,
            'size_bytes': size,
            'size_formatted': format_file_size(size),
            'modified_timestamp': mtime,
            'modified_formatted': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S') if mtime else '',
            'inferred_date': inferred_date,
            'is_primary': is_primary,
        }

    def resolve_file_path(self, file_name):
        """
        Resolves a file name to its absolute path.
        """
        all_files = self.get_available_files()
        if not file_name and all_files:
            return all_files[0]['path'], all_files[0]['name']

        for f in all_files:
            if f['name'] == file_name or f['path'] == file_name:
                return f['path'], f['name']

        # Fallback via LogManager load_details
        self.log_manager.load_details(file_name)
        if self.log_manager.path:
            full_path = os.path.join(self.log_manager.path, file_name)
            if os.path.isfile(full_path):
                return full_path, file_name

        return None, file_name

    def sanitize_payload(self, text):
        """
        Sanitizes massive payloads, large arrays, giant JSON objects,
        base64 blobs, and sensitive tokens for table list view DOM protection.
        """
        if not config.sanitization_enabled() or not text:
            return {
                'sanitized': text or '',
                'was_sanitized': False,
                'stripped_chars': 0,
                'stripped_items': 0,
            }

        orig_len = len(text)
        was_sanitized = False
        stripped_items = 0

        # 1. Strip large arrays / collections (e.g. [item1, item2, ...])
        def replace_large_array(m):
            nonlocal was_sanitized, stripped_items
            inner = m.group(1)
            items = [item.strip() for item in inner.split(',') if item.strip()]
            max_items = config.array_max_items()
            if len(items) > max_items:
                was_sanitized = True
                stripped_items += len(items)
                return f"[/* 📦 Array ({len(items)} items) stripped */]"
            return m.group(0)

        text = re.sub(r'\[([^\]\n]{60,})\]', replace_large_array, text)

        # 2. Strip base64 blobs
        def replace_base64(m):
            nonlocal was_sanitized
            blob = m.group(0)
            if len(blob) > 60:
                was_sanitized = True
                return f"[/* 🔑 Base64 blob ({len(blob)} chars) stripped */]"
            return blob

        text = re.sub(r'(?:data:[a-zA-Z0-9/+-]+;base64,)?[A-Za-z0-9+/=]{80,}', replace_base64, text)

        # 4. Strip massive JSON objects
        def replace_json_obj(m):
            nonlocal was_sanitized
            obj_str = m.group(0)
            max_len = config.payload_max_length()
            if len(obj_str) > max_len:
                was_sanitized = True
                return f"[/* 📦 Object ({len(obj_str):,} chars) stripped */]"
            return obj_str

        text = re.sub(r'\{[^{}\n]{150,}\}', replace_json_obj, text)

        # 5. Mask Authorization Bearer tokens & passwords
        text = re.sub(r'(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{15,}', r'\1[REDACTED_TOKEN]', text)
        text = re.sub(r'(?i)(["\']?password["\']?\s*[:=]\s*["\'])[^"\']+(["\'])', r'\1********\2', text)

        # 6. Fallback string truncation for any inline string that is still too long
        max_str_len = config.payload_max_length() * 2
        if len(text) > max_str_len:
            was_sanitized = True
            diff = len(text) - max_str_len
            text = text[:max_str_len] + f" [/* 📄 +{diff:,} more chars stripped */]"

        stripped_chars = max(0, orig_len - len(text))
        return {
            'sanitized': text,
            'was_sanitized': was_sanitized,
            'stripped_chars': stripped_chars,
            'stripped_items': stripped_items,
        }

    def extract_entity_ids(self, text):
        """
        Extracts entity/correlation IDs (Requests, Traces, Correlation IDs, Users, Tasks, Orders, UUIDs, #ID).
        """
        if not text:
            return []
        found = []
        for pat in self.compiled_entity_patterns:
            for m in pat.finditer(text):
                val = m.group(1).strip()
                if val and val not in found and len(val) <= 64:
                    found.append(val)
        return found

    def map_lifecycle_stage(self, message, level='INFO'):
        """
        Maps a log message to an entity / transaction lifecycle stage.
        """
        msg_lower = (message or '').lower()
        level_upper = (level or '').upper()

        if level_upper in ('ERROR', 'CRITICAL', 'EXCEPTION', 'FATAL'):
            return {
                'name': 'Failures / Errors',
                'color': 'red',
            }

        stages = config.lifecycle_stages()
        for stage in stages:
            for kw in stage.get('keywords', []):
                if re.search(r'\b' + re.escape(kw) + r'\b', msg_lower):
                    return {
                        'name': stage['name'],
                        'color': stage['color'],
                    }

        return {
            'name': 'Execution / Event',
            'color': 'cyan',
        }

    def _normalize_level(self, raw_level):
        lvl = (raw_level or '').strip().upper()
        if lvl in ('WARNING', 'WARN'):
            return 'WARN'
        if lvl in ('CRITICAL', 'FATAL', 'EXCEPTION'):
            return 'CRITICAL'
        if lvl in ('ERROR', 'ERR'):
            return 'ERROR'
        if lvl in ('INFO', 'INFORMATION'):
            return 'INFO'
        if lvl in ('DEBUG', 'TRACE'):
            return 'DEBUG'
        return lvl or 'INFO'

    def parse_entry_from_row(self, row, columns, file_name, line_idx=0):
        """
        Converts a parsed row list from LogManager into a rich log entry object.
        """
        data = dict(zip(columns, row))
        date_val = data.get('Date', '')
        time_val = data.get('Time', '')
        timestamp = f"{date_val} {time_val}".strip() or data.get('Server Time', '') or data.get('Asctime', '')
        raw_level = data.get('Levelname', '') or data.get('Level', '')
        level = self._normalize_level(raw_level)
        logger_name = data.get('Name', '') or data.get('Module', '') or file_name
        message = data.get('Message', '') or data.get('Log', '')

        if not message and columns:
            message = str(row[-1])

        sanitized_info = self.sanitize_payload(message)
        entities = self.extract_entity_ids(message)

        # Parse hour for 24-hr histogram
        hour_str = None
        if time_val and ':' in time_val:
            hour_str = time_val.split(':')[0].strip().zfill(2)
        elif timestamp:
            tm = re.search(r'\b(\d{2}):\d{2}', timestamp)
            if tm:
                hour_str = tm.group(1).zfill(2)

        return {
            'id': f"{file_name}:{line_idx}",
            'file': file_name,
            'timestamp': timestamp,
            'date': date_val,
            'time': time_val,
            'hour': hour_str,
            'level': level,
            'logger': logger_name,
            'entities': entities,
            'primary_entity': entities[0] if entities else None,
            'message': message,
            'sanitized_message': sanitized_info['sanitized'],
            'was_sanitized': sanitized_info['was_sanitized'],
            'stripped_chars': sanitized_info['stripped_chars'],
            'raw_row': row,
        }

    def get_overview(self, file_name=None, date=None):
        """
        Calculates KPIs, severity counts, and 24-hour traffic distribution.
        Uses in-memory cache to guarantee sub-millisecond repeated queries.
        """
        file_path, resolved_name = self.resolve_file_path(file_name)
        if not file_path or not os.path.isfile(file_path):
            return {
                'file_name': resolved_name or 'None',
                'file_size_bytes': 0,
                'file_size_formatted': '0 B',
                'total_entries': 0,
                'levels_count': {'all': 0, 'critical': 0, 'error': 0, 'warn': 0, 'info': 0, 'debug': 0},
                'error_count': 0,
                'error_rate': '0.00%',
                'warning_count': 0,
                'info_count': 0,
                'debug_count': 0,
                'hourly_traffic': [{'hour': f"{h:02d}:00", 'count': 0, 'error_count': 0} for h in range(24)],
                'peak_hour': None,
                'has_traffic_surge': False,
                'cache_hit': False,
            }

        try:
            mtime = os.path.getmtime(file_path)
            size_bytes = os.path.getsize(file_path)
        except OSError:
            mtime = 0
            size_bytes = 0

        cache_key = (file_path, mtime, date)
        if config.cache_enabled() and cache_key in self._overview_cache:
            res = dict(self._overview_cache[cache_key])
            res['cache_hit'] = True
            return res

        self.log_manager.load_details(resolved_name)
        rows = self.log_manager.get_log_content(resolved_name)
        columns = self.log_manager.get_columns()

        levels_count = {
            'all': 0,
            'critical': 0,
            'error': 0,
            'warn': 0,
            'info': 0,
            'debug': 0,
        }
        hourly_counts = {h: 0 for h in range(24)}
        hourly_errors = {h: 0 for h in range(24)}

        for idx, row in enumerate(rows):
            entry = self.parse_entry_from_row(row, columns, resolved_name, idx)
            # Date filter if requested
            if date and entry['date'] and entry['date'] != date:
                continue

            lvl = entry['level'].lower()
            levels_count['all'] += 1
            if lvl in levels_count:
                levels_count[lvl] += 1
            elif lvl == 'warning':
                levels_count['warn'] += 1
            elif lvl in ('fatal', 'exception'):
                levels_count['critical'] += 1
            else:
                levels_count['info'] += 1

            if entry['hour'] and entry['hour'].isdigit():
                h_int = int(entry['hour'])
                if 0 <= h_int < 24:
                    hourly_counts[h_int] += 1
                    if lvl in ('error', 'critical', 'fatal', 'exception'):
                        hourly_errors[h_int] += 1

        total = levels_count['all']
        error_total = levels_count['error'] + levels_count['critical']
        error_rate = f"{(error_total / total * 100):.2f}%" if total > 0 else "0.00%"

        hourly_traffic = [
            {
                'hour': f"{h:02d}:00",
                'hour_num': h,
                'count': hourly_counts[h],
                'error_count': hourly_errors[h],
            }
            for h in range(24)
        ]

        # Peak calculation
        peak_entry = max(hourly_traffic, key=lambda x: x['count']) if total > 0 else None
        avg_hourly = total / 24.0 if total > 0 else 0
        has_surge = bool(peak_entry and peak_entry['count'] > 0 and peak_entry['count'] > (avg_hourly * 2.2))

        result = {
            'file_name': resolved_name,
            'file_size_bytes': size_bytes,
            'file_size_formatted': format_file_size(size_bytes),
            'total_entries': total,
            'levels_count': levels_count,
            'error_count': error_total,
            'error_rate': error_rate,
            'warning_count': levels_count['warn'],
            'info_count': levels_count['info'],
            'debug_count': levels_count['debug'],
            'hourly_traffic': hourly_traffic,
            'peak_hour': peak_entry['hour'] if peak_entry and peak_entry['count'] > 0 else None,
            'peak_count': peak_entry['count'] if peak_entry else 0,
            'has_traffic_surge': has_surge,
            'cache_hit': False,
        }

        if config.cache_enabled():
            # Store in cache
            if len(self._overview_cache) > 50:
                self._overview_cache.clear()
            self._overview_cache[cache_key] = result

        return result

    def get_logs_page(
        self,
        file_name=None,
        level=None,
        keyword=None,
        entity_id=None,
        page=1,
        limit=None,
        reverse=None,
        all_files=False,
    ):
        """
        Retrieves a paginated list of sanitized log entries with fast filtering.
        """
        limit = int(limit) if limit else config.page_size()
        page = max(1, int(page) if page else 1)
        reverse = config.reverse_order() if reverse is None else bool(reverse)

        files_to_scan = []
        if all_files:
            files_to_scan = [f['name'] for f in self.get_available_files()]
        else:
            _, resolved_name = self.resolve_file_path(file_name)
            files_to_scan = [resolved_name] if resolved_name else []

        matching_entries = []
        keyword_lower = keyword.strip().lower() if keyword else None
        level_filter = level.strip().upper() if level and level.upper() != 'ALL' else None
        entity_filter = str(entity_id).strip() if entity_id else None

        for fname in files_to_scan:
            self.log_manager.load_details(fname)
            rows = self.log_manager.get_log_content(fname)
            columns = self.log_manager.get_columns()

            for idx, row in enumerate(rows):
                entry = self.parse_entry_from_row(row, columns, fname, idx)

                # Filter by level
                if level_filter:
                    lvl = entry['level'].upper()
                    if level_filter == 'WARN' and lvl not in ('WARN', 'WARNING'):
                        continue
                    elif level_filter == 'ERROR' and lvl not in ('ERROR', 'CRITICAL', 'FATAL'):
                        continue
                    elif level_filter not in ('WARN', 'ERROR') and lvl != level_filter:
                        continue

                # Filter by keyword
                if keyword_lower:
                    searchable = f"{entry['timestamp']} {entry['level']} {entry['logger']} {entry['message']}".lower()
                    if keyword_lower not in searchable:
                        continue

                # Filter by entity
                if entity_filter:
                    matched_entity = False
                    for ent in entry['entities']:
                        if entity_filter.lower() in ent.lower():
                            matched_entity = True
                            break
                    if not matched_entity and entity_filter.lower() not in entry['message'].lower():
                        continue

                matching_entries.append(entry)

        if reverse:
            matching_entries.reverse()

        total_matched = len(matching_entries)
        total_pages = max(1, (total_matched + limit - 1) // limit)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paged_items = matching_entries[start_idx:end_idx]

        return {
            'entries': paged_items,
            'total_matched': total_matched,
            'page': page,
            'limit': limit,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        }

    def scan_entity(
        self,
        entity_id,
        file_name=None,
        date_scope='selected',
        start_date=None,
        end_date=None,
        level_filter=None,
    ):
        """
        Targeted entity / correlation scanner (e.g. Request ID, Trace ID, User ID, Task ID).
        Extracts correlated lifecycle events, level breakdown, and chronological timeline.
        """
        start_time = time.time()
        entity_str = str(entity_id).strip()
        level_req = level_filter.strip().upper() if level_filter and level_filter.upper() != 'ALL' else None

        # Determine target files
        available_files = self.get_available_files()
        target_files = []

        if date_scope == 'all':
            target_files = available_files
        elif date_scope == 'range' and (start_date or end_date):
            for f in available_files:
                f_date = f.get('inferred_date')
                if f_date:
                    if start_date and f_date < start_date:
                        continue
                    if end_date and f_date > end_date:
                        continue
                target_files.append(f)
        else:
            _, resolved_name = self.resolve_file_path(file_name)
            target_files = [f for f in available_files if f['name'] == resolved_name]
            if not target_files and available_files:
                target_files = [available_files[0]]

        levels_count = {
            'all': 0,
            'error': 0,
            'warn': 0,
            'info': 0,
            'debug': 0,
            'critical': 0,
        }
        all_matched_events = []

        # Entity regex variants
        entity_regex = re.compile(
            rf'(?i)(?:\b(?:id|request|req|trace|correlation|user|task|order|tx)[_:\s#=]+|#)?\b{re.escape(entity_str)}\b'
        )

        for f_info in target_files:
            fname = f_info['name']
            self.log_manager.load_details(fname)
            rows = self.log_manager.get_log_content(fname)
            columns = self.log_manager.get_columns()

            for idx, row in enumerate(rows):
                entry = self.parse_entry_from_row(row, columns, fname, idx)

                # Check if entity is present in entities list or message
                matched = any(entity_str.lower() == e.lower() for e in entry['entities'])
                if not matched and entity_regex.search(entry['message']):
                    matched = True

                if not matched:
                    continue

                lvl_key = entry['level'].lower()
                levels_count['all'] += 1
                if lvl_key in levels_count:
                    levels_count[lvl_key] += 1
                elif lvl_key == 'warning':
                    levels_count['warn'] += 1
                elif lvl_key in ('fatal', 'exception'):
                    levels_count['critical'] += 1
                else:
                    levels_count['info'] += 1

                # If level filtering is active, skip non-matching events from timeline
                if level_req:
                    lvl_up = entry['level'].upper()
                    if level_req == 'WARN' and lvl_up not in ('WARN', 'WARNING'):
                        continue
                    elif level_req == 'ERROR' and lvl_up not in ('ERROR', 'CRITICAL', 'FATAL'):
                        continue
                    elif level_req not in ('WARN', 'ERROR') and lvl_up != level_req:
                        continue

                stage_info = self.map_lifecycle_stage(entry['message'], entry['level'])

                all_matched_events.append({
                    'id': entry['id'],
                    'file': fname,
                    'timestamp': entry['timestamp'],
                    'date': entry['date'],
                    'time': entry['time'],
                    'level': entry['level'],
                    'logger': entry['logger'],
                    'stage': stage_info['name'],
                    'stage_color': stage_info['color'],
                    'message_sanitized': entry['sanitized_message'],
                    'was_sanitized': entry['was_sanitized'],
                    'raw_message': entry['message'],
                })

        # Sort timeline chronologically
        all_matched_events.sort(key=lambda x: x['timestamp'] or '')
        for idx, ev in enumerate(all_matched_events):
            ev['step'] = idx + 1

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        scope_desc = 'Selected File'
        if date_scope == 'all':
            scope_desc = f'All Available Files ({len(target_files)} files)'
        elif date_scope == 'range':
            scope_desc = f'Date Range: {start_date or "earliest"} to {end_date or "latest"}'

        return {
            'entity_id': entity_str,
            'total_found': len(all_matched_events),
            'levels_count': levels_count,
            'elapsed_ms': elapsed_ms,
            'scope': scope_desc,
            'timeline': all_matched_events,
        }

    def get_log_detail(self, detail_id):
        """
        Retrieves the complete, un-truncated raw log payload for the detail modal.
        """
        if not detail_id or ':' not in detail_id:
            return None

        file_name, line_idx_str = detail_id.split(':', 1)
        try:
            line_idx = int(line_idx_str)
        except ValueError:
            return None

        file_path, resolved_name = self.resolve_file_path(file_name)
        if not file_path or not os.path.isfile(file_path):
            return None

        self.log_manager.load_details(resolved_name)
        rows = self.log_manager.get_log_content(resolved_name)
        columns = self.log_manager.get_columns()

        if 0 <= line_idx < len(rows):
            entry = self.parse_entry_from_row(rows[line_idx], columns, resolved_name, line_idx)
            raw_msg = entry['message']

            # Check if raw_msg contains valid JSON
            is_json = False
            json_parsed = None
            trimmed_msg = raw_msg.strip()
            if (trimmed_msg.startswith('{') and trimmed_msg.endswith('}')) or (
                trimmed_msg.startswith('[') and trimmed_msg.endswith(']')
            ):
                try:
                    json_parsed = json.loads(trimmed_msg)
                    is_json = True
                except Exception:
                    pass

            return {
                'id': detail_id,
                'file': resolved_name,
                'timestamp': entry['timestamp'],
                'date': entry['date'],
                'time': entry['time'],
                'level': entry['level'],
                'logger': entry['logger'],
                'entities': entry['entities'],
                'primary_entity': entry['primary_entity'],
                'raw_message': raw_msg,
                'is_json': is_json,
                'json_data': json_parsed,
                'was_sanitized': entry['was_sanitized'],
                'stripped_chars': entry['stripped_chars'],
            }

        return None

    def export_data(self, file_name=None, export_format='json', level=None, keyword=None):
        """
        Exports log entries as JSON string or CSV string.
        """
        logs_res = self.get_logs_page(
            file_name=file_name,
            level=level,
            keyword=keyword,
            page=1,
            limit=config.max_lines(),
            reverse=False,
        )
        entries = logs_res['entries']

        if export_format.lower() == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'File', 'Timestamp', 'Level', 'Logger', 'Entities', 'Message'])
            for e in entries:
                writer.writerow([
                    e['id'],
                    e['file'],
                    e['timestamp'],
                    e['level'],
                    e['logger'],
                    ', '.join(e['entities']),
                    e['message'],
                ])
            return output.getvalue(), 'text/csv'
        else:
            export_payload = [
                {
                    'id': e['id'],
                    'file': e['file'],
                    'timestamp': e['timestamp'],
                    'level': e['level'],
                    'logger': e['logger'],
                    'entities': e['entities'],
                    'message': e['message'],
                }
                for e in entries
            ]
            return json.dumps(export_payload, indent=2), 'application/json'
