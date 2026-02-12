"""Lightweight HTTP worker for multiprocessing subprocess.

This module is intentionally kept free of any katrain/kivy imports
so that it can be safely imported in a spawned subprocess without
triggering the heavy dependency chain.
"""

import logging


def do_request(url, payload, headers, timeout, conn):
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    try:
        import requests

        response = requests.post(url, json=payload, headers=headers, timeout=timeout)

        if response.status_code >= 400:
            conn.send({"error": f"HTTP {response.status_code}"})
        else:
            try:
                data = response.json()
            except Exception as e:
                raise e

            try:
                conn.send({"data": data})
            except Exception as e:
                raise e

    except Exception as e:
        try:
            conn.send({"error": str(e)})
        except:
            pass
    finally:
        conn.close()
