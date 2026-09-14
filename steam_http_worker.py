"""One isolated HTTP attempt. Input/output travel only through private pipes."""
import base64
import json
import sys
import requests


class NoRedirectSession(requests.Session):
    def resolve_redirects(self, *args, **kwargs):
        # Requests otherwise consumes redirect bodies while preparing Response.next,
        # even when allow_redirects=False and stream=True.
        return iter(())


def main():
    try:
        job = json.load(sys.stdin)
        with NoRedirectSession() as session, session.get(job['url'], params=job['params'], timeout=job['timeout'],
                                                        allow_redirects=False, stream=True) as response:
            body = bytearray()
            if response.status_code == 200:
                for chunk in response.iter_content(min(65536, job['max_bytes'] + 1)):
                    body.extend(chunk)
                    if len(body) > job['max_bytes']:
                        print(json.dumps({'error': 'HTTP_RESPONSE_TOO_LARGE'}))
                        return
            result = {'status': response.status_code, 'headers': dict(response.headers),
                      'body': base64.b64encode(body).decode('ascii')}
        print(json.dumps(result))
    except requests.Timeout:
        print(json.dumps({'error': 'HTTP_TIMEOUT'}))
    except Exception:
        print(json.dumps({'error': 'HTTP_TRANSPORT_FAILED'}))


if __name__ == '__main__':
    main()
