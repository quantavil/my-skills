// A stand-in for ASP.NET's PageRequestManager, so postback logic can be tested without ImpexCube.
type Handler = (
  sender: unknown,
  args: { get_error(): Error | null; set_errorHandled(h: boolean): void },
) => void;

export interface FakeManager {
  inAsync: boolean;
  starts: Handler[];
  ends: Handler[];
  /** Simulates one async postback that lasts `ms`. */
  postback(ms?: number, error?: Error): void;
}

export function installFakeSys(): FakeManager {
  const fake: FakeManager = {
    inAsync: false,
    starts: [],
    ends: [],
    postback(ms = 5, error) {
      fake.inAsync = true;
      for (const handler of [...fake.starts]) handler(fake, { get_error: () => null, set_errorHandled() {} });
      setTimeout(() => {
        fake.inAsync = false;
        for (const handler of [...fake.ends])
          handler(fake, { get_error: () => error ?? null, set_errorHandled() {} });
      }, ms);
    },
  };
  const remove = (list: Handler[], handler: Handler) => {
    const at = list.indexOf(handler);
    if (at >= 0) list.splice(at, 1);
  };
  const manager = {
    get_isInAsyncPostBack: () => fake.inAsync,
    add_initializeRequest: (h: Handler) => fake.starts.push(h),
    remove_initializeRequest: (h: Handler) => remove(fake.starts, h),
    add_endRequest: (h: Handler) => fake.ends.push(h),
    remove_endRequest: (h: Handler) => remove(fake.ends, h),
  };
  Object.assign(globalThis, { Sys: { WebForms: { PageRequestManager: { getInstance: () => manager } } } });
  return fake;
}
