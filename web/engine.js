// Talks to the Pyodide worker. One compose runs at a time; while it runs, only the
// newest waiting request is kept (older waiting requests resolve to null).

export class Engine {
  constructor(worker, { onProgress } = {}) {
    this.worker = worker;
    this.onProgress = onProgress;
    this.nextId = 1;
    this.calls = new Map();
    this.busy = false;
    this.pending = null;
    worker.onmessage = (event) => this._receive(event.data);
  }

  _receive(msg) {
    if (msg.progress !== undefined) {
      this.onProgress?.(msg);
      return;
    }
    const call = this.calls.get(msg.id);
    if (!call) return;
    this.calls.delete(msg.id);
    if (msg.ok) call.resolve(msg.result);
    else call.reject(Object.assign(new Error(msg.error), { kind: msg.kind }));
  }

  _send(op, params) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.calls.set(id, { resolve, reject });
      this.worker.postMessage({ id, op, params });
    });
  }

  compose(params) {
    if (this.busy) {
      this.pending?.resolve(null);
      return new Promise((resolve, reject) => {
        this.pending = { params, resolve, reject };
      });
    }
    this.busy = true;
    return this._send("compose", params)
      .then((result) => (this.pending ? null : result)) // a newer request replaced this one
      .finally(() => {
      this.busy = false;
      const next = this.pending;
      this.pending = null;
      if (next) this.compose(next.params).then(next.resolve, next.reject);
    });
  }

  midi(params) {
    return this._send("midi", params);
  }
}
