#import <Cocoa/Cocoa.h>
#import <IOSurface/IOSurface.h>
#include <dlfcn.h>
#include <cstdio>
#include <iostream>
#include <thread>
#include <mutex>
#include <vector>
#include <map>
#include "include/cef_app.h"
#include "include/cef_parser.h"
#include "include/cef_task.h"
#include "include/cef_devtools_message_observer.h"
#include "include/cef_application_mac.h"
#include "include/cef_version.h"
#include "include/cef_command_line.h"
#include "include/cef_request_handler.h"
#include "include/cef_jsdialog_handler.h"
#include "include/base/cef_callback.h"
#include "include/wrapper/cef_helpers.h"
#include "include/wrapper/cef_library_loader.h"
#include "include/base/cef_bind.h"
#include "include/wrapper/cef_closure_task.h"

// CEF requires an NSApplication implementing this protocol even without windows.
@interface RendererApplication : NSApplication <CefAppProtocol> { BOOL sending_; }
@end
@implementation RendererApplication
- (BOOL)isHandlingSendEvent { return sending_; }
- (void)setHandlingSendEvent:(BOOL)value { sending_ = value; }
- (void)sendEvent:(NSEvent*)event {
  CefScopedSendingEvent scope;
  [super sendEvent:event];
}
@end

void Reply(int id, CefRefPtr<CefDictionaryValue> result, const std::string& error = "") {
  auto value = CefDictionaryValue::Create();
  value->SetInt("id", id);
  if (result) value->SetDictionary("result", result);
  if (!error.empty()) value->SetString("error", error);
  auto envelope = CefValue::Create();
  envelope->SetDictionary(value);
  std::cout << CefWriteJSON(envelope, JSON_WRITER_DEFAULT).ToString() << std::endl;
}

class Renderer : public CefApp, public CefBrowserProcessHandler,
                 public CefClient, public CefRenderHandler,
                 public CefLifeSpanHandler, public CefLoadHandler,
                 public CefRequestHandler, public CefResourceRequestHandler, public CefJSDialogHandler,
                 public CefDevToolsMessageObserver {
 public:
  CefRefPtr<CefBrowserProcessHandler> GetBrowserProcessHandler() override { return this; }
  CefRefPtr<CefRenderHandler> GetRenderHandler() override { return this; }
  CefRefPtr<CefLifeSpanHandler> GetLifeSpanHandler() override { return this; }
  CefRefPtr<CefLoadHandler> GetLoadHandler() override { return this; }
  CefRefPtr<CefRequestHandler> GetRequestHandler() override { return this; }
  CefRefPtr<CefJSDialogHandler> GetJSDialogHandler() override { return this; }
  bool OnJSDialog(CefRefPtr<CefBrowser>, const CefString&, JSDialogType,
                  const CefString&, const CefString&, CefRefPtr<CefJSDialogCallback>,
                  bool& suppress) override {
    suppress = true;
    std::lock_guard<std::mutex> guard(resources_);
    if (errors_.size() < 100) errors_.push_back("Interactive JavaScript dialog unsupported by background renderer");
    return false;
  }
  bool OnBeforeUnloadDialog(CefRefPtr<CefBrowser>, const CefString&, bool,
                            CefRefPtr<CefJSDialogCallback> callback) override {
    callback->Continue(true, "");
    std::lock_guard<std::mutex> guard(resources_);
    if (errors_.size() < 100) errors_.push_back("Interactive before-unload dialog unsupported by background renderer");
    return true;
  }
  bool OnBeforePopup(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>, int,
      const CefString&, const CefString&, WindowOpenDisposition, bool,
      const CefPopupFeatures&, CefWindowInfo&, CefRefPtr<CefClient>&,
      CefBrowserSettings&, CefRefPtr<CefDictionaryValue>&, bool*) override {
    std::lock_guard<std::mutex> guard(resources_);
    if (errors_.size() < 100) errors_.push_back("Popup windows unsupported by background renderer");
    return true;
  }
  CefRefPtr<CefResourceRequestHandler> GetResourceRequestHandler(CefRefPtr<CefBrowser>,
      CefRefPtr<CefFrame>, CefRefPtr<CefRequest>, bool, bool, const CefString&, bool&) override { return this; }
  ReturnValue OnBeforeResourceLoad(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>,
      CefRefPtr<CefRequest> request, CefRefPtr<CefCallback>) override {
    const std::string url = request->GetURL();
    std::lock_guard<std::mutex> guard(resources_);
    if (url.rfind(origin_, 0) == 0 || url.rfind("data:", 0) == 0 ||
        url.rfind("blob:", 0) == 0 || url == "about:blank") return RV_CONTINUE;
    if (errors_.size() < 100) errors_.push_back("Unbundled resource blocked: " + url);
    return RV_CANCEL;
  }
  void OnContextInitialized() override {
    std::cerr << "VibeEdit CEF context initialized" << std::endl;
    CefWindowInfo window;
    window.SetAsWindowless(nullptr);
    window.shared_texture_enabled = true;
    window.external_begin_frame_enabled = true;
    CefBrowserSettings settings;
    settings.windowless_frame_rate = 60;
    const bool created = CefBrowserHost::CreateBrowser(window, this, "about:blank", settings, nullptr, nullptr);
    std::cerr << "VibeEdit browser creation requested: " << created << std::endl;
  }
  void OnAfterCreated(CefRefPtr<CefBrowser> browser) override {
    browser_ = browser;
    browser_->GetHost()->SetAudioMuted(true);
    registration_ = browser->GetHost()->AddDevToolsMessageObserver(this);
    auto result = CefDictionaryValue::Create();
    result->SetString("browser", CEF_VERSION);
    result->SetInt("windows", static_cast<int>(NSApp.windows.count));
    result->SetBool("active", NSApp.isActive);
    Reply(0, result);
    // One command in flight. The orchestrator supplies deadlines and process-group cleanup.
    std::thread([self = CefRefPtr<Renderer>(this)] {
      std::string line;
      while (std::getline(std::cin, line)) {
        CefPostTask(TID_UI, base::BindOnce(&Renderer::Command, self, line));
      }
      CefPostTask(TID_UI, base::BindOnce(&Renderer::Close, self));
    }).detach();
  }
  void GetViewRect(CefRefPtr<CefBrowser>, CefRect& rect) override { rect = CefRect(0, 0, width_, height_); }
  bool GetScreenInfo(CefRefPtr<CefBrowser>, CefScreenInfo& screen) override {
    screen.device_scale_factor = 1;
    screen.rect = screen.available_rect = CefRect(0, 0, width_, height_);
    return true;
  }
  void OnPaint(CefRefPtr<CefBrowser>, PaintElementType, const RectList&, const void*, int, int) override {}
  void OnAcceleratedPaint(CefRefPtr<CefBrowser>, PaintElementType type, const RectList&,
                          const CefAcceleratedPaintInfo& info) override {
    if (type != PET_VIEW || capture_ == 0) return;
    auto surface = static_cast<IOSurfaceRef>(info.shared_texture_io_surface);
    if (IOSurfaceGetWidth(surface) != static_cast<size_t>(width_) ||
        IOSurfaceGetHeight(surface) != static_cast<size_t>(height_)) return;
    // Drain a possibly already-submitted capture before invalidating again.
    // JS completion and an arbitrary queued Viz callback are different fences.
    if (draining_) {
      draining_ = false;
      CefPostTask(TID_UI, base::BindOnce(&Renderer::Refresh, CefRefPtr<Renderer>(this)));
      return;
    }
    const int id = capture_;
    capture_ = 0;
    const int accepted = barrier_only_ ? 1 : submit_ ? submit_(surface, frame_) : 0;
    auto result = CefDictionaryValue::Create();
    result->SetInt("frame", frame_);
    result->SetDouble("captureCounter", static_cast<double>(info.extra.capture_counter));
    if (!barrier_only_ && metric_) {
      result->SetDouble("gpuTransferConversionSeconds", metric_(0));
      result->SetDouble("nativeWaitSeconds", metric_(1));
      result->SetDouble("encoderAppendSeconds", metric_(2));
    }
    Reply(id, result, accepted ? "" : "GPU copy/encode failed");
  }
  void OnLoadEnd(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame> frame, int status) override {
    if (!frame->IsMain() || !load_) return;
    if (frame->GetURL().ToString() != load_url_) return;
    const int id = load_;
    load_ = 0;
    Reply(id, CefDictionaryValue::Create(), status >= 400 ? "document load failed" : "");
  }
  void OnLoadError(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame> frame, ErrorCode,
                   const CefString& text, const CefString&) override {
    if (!frame->IsMain() || !load_) return;
    Reply(load_, nullptr, text.ToString());
    load_ = 0;
  }
  void OnDevToolsMethodResult(CefRefPtr<CefBrowser>, int id, bool success,
                              const void* result, size_t size) override {
    const auto request = protocol_requests_.find(id);
    if (request == protocol_requests_.end()) return;
    const int rpc = request->second;
    protocol_requests_.erase(request);
    const auto value = CefParseJSON(static_cast<const char*>(result), size, JSON_PARSER_RFC);
    Reply(rpc, value && value->GetType() == VTYPE_DICTIONARY ? value->GetDictionary() : nullptr,
          success ? "" : std::string(static_cast<const char*>(result), size));
    evaluating_ = false;
    evaluate_id_ = 0;
  }
  void OnRenderProcessTerminated(CefRefPtr<CefBrowser>, TerminationStatus status,
                                 int error_code, const CefString& text) override {
    const std::string error = "render-process-terminated status=" + std::to_string(status) +
      " code=" + std::to_string(error_code) + " " + text.ToString();
    const int id = capture_ ? capture_ : load_ ? load_ : evaluate_id_;
    if (id) Reply(id, nullptr, error);
    capture_ = load_ = evaluate_id_ = 0;
    protocol_requests_.clear();
    evaluating_ = false;
    std::lock_guard<std::mutex> guard(resources_);
    if (errors_.size() < 100) errors_.push_back(error);
  }
  void OnDevToolsEvent(CefRefPtr<CefBrowser>, const CefString& method,
                      const void* params, size_t size) override {
    const std::string event = method;
    const auto value = CefParseJSON(static_cast<const char*>(params), size, JSON_PARSER_RFC);
    if (!value || value->GetType() != VTYPE_DICTIONARY) return;
    auto data = value->GetDictionary();
    if (event == "Tracing.dataCollected") {
      auto values = data->GetList("value");
      for (size_t i = 0; values && i < values->GetSize(); ++i) {
        auto item = values->GetDictionary(i);
        if (item->GetString("ph") != "X" || !item->HasKey("dur")) continue;
        const std::string name = item->GetString("name");
        if (trace_.size() >= 256 && !trace_.count(name)) continue;
        trace_[name].first += (item->GetType("dur") == VTYPE_INT ? item->GetInt("dur") : item->GetDouble("dur")) / 1000000.0;
        trace_[name].second += 1;
      }
      return;
    }
    if (event == "Tracing.tracingComplete") { trace_complete_ = true; return; }
    // Media range readers routinely abort superseded requests; navigation also
    // cancels the previous document. Decoder errors are checked by the adapter.
    if (event == "Network.loadingFailed" && data->GetBool("canceled")) return;
    // Chromium requests a favicon even for documents that don't declare one.
    // Its absence doesn't affect composition pixels or executable dependencies.
    if (event == "Network.responseReceived" && data->GetString("type") == "Other") {
      const std::string url = data->GetDictionary("response")->GetString("url");
      if (url.size() >= 12 && url.substr(url.size()-12) == "/favicon.ico") return;
    }
    const bool resource_error = event == "Network.responseReceived" &&
      data->GetDictionary("response")->GetInt("status") >= 400;
    if (event != "Runtime.exceptionThrown" && event != "Network.loadingFailed" && !resource_error) return;
    std::lock_guard<std::mutex> guard(resources_);
    // Bounded diagnostics, preserving a failure rather than hiding dropped resources.
    if (errors_.size() < 100) errors_.push_back(event + ": " + std::string(static_cast<const char*>(params), size));
  }
  void OnBeforeClose(CefRefPtr<CefBrowser>) override {
    registration_ = nullptr;
    browser_ = nullptr;
    CefQuitMessageLoop();
  }
  void Close() { if (browser_) browser_->GetHost()->CloseBrowser(true); }
  void Command(const std::string& line) {
    const auto value = CefParseJSON(line, JSON_PARSER_RFC);
    if (!value || value->GetType() != VTYPE_DICTIONARY) return;
    const auto command = value->GetDictionary();
    const int id = command->GetInt("id");
    const std::string method = command->GetString("method");
    if (method == "load") {
      width_ = command->GetInt("width");
      height_ = command->GetInt("height");
      load_ = id;
      load_url_ = command->GetString("url").ToString();
      {
        std::lock_guard<std::mutex> guard(resources_);
        origin_ = load_url_.substr(0, load_url_.find('/', load_url_.find("://") + 3) + 1);
        errors_.clear();
      }
      browser_->GetHost()->WasResized();
      browser_->GetMainFrame()->LoadURL(command->GetString("url"));
      Pump();
      return;
    }
    if (method == "trace.reset") {
      trace_.clear(); trace_complete_ = false;
      Reply(id, nullptr); return;
    }
    if (method == "trace.read") {
      auto result = CefDictionaryValue::Create();
      auto events = CefDictionaryValue::Create();
      for (const auto& item : trace_) {
        auto measured = CefDictionaryValue::Create();
        measured->SetDouble("durationSeconds", item.second.first);
        measured->SetInt("count", item.second.second);
        events->SetDictionary(item.first, measured);
      }
      result->SetBool("complete", trace_complete_); result->SetDictionary("events", events);
      Reply(id, result); return;
    }
    if (method == "diagnostics") {
      auto result = CefDictionaryValue::Create();
      auto errors = CefListValue::Create();
      std::lock_guard<std::mutex> guard(resources_);
      for (size_t i = 0; i < errors_.size(); ++i) errors->SetString(i, errors_[i]);
      result->SetList("errors", errors);
      Reply(id, result);
      return;
    }
    if (method == "begin") {
      if (!library_) {
        library_ = dlopen(command->GetString("bridge").ToString().c_str(), RTLD_NOW | RTLD_LOCAL);
        if (library_) {
          begin_ = reinterpret_cast<Begin>(dlsym(library_, "vibeedit_renderer_begin"));
          submit_ = reinterpret_cast<Submit>(dlsym(library_, "vibeedit_renderer_submit"));
          finish_ = reinterpret_cast<Finish>(dlsym(library_, "vibeedit_renderer_finish"));
          metric_ = reinterpret_cast<Metric>(dlsym(library_, "vibeedit_renderer_metric"));
        }
      }
      const int accepted = begin_ ? begin_(command->GetString("output").ToString().c_str(),
        command->GetString("raw").ToString().c_str(), width_, height_,
        command->GetInt("numerator"), command->GetInt("denominator"), command->GetInt("bitrate")) : 0;
      Reply(id, nullptr, accepted ? "" : "encoder initialization failed");
      return;
    }
    if (method == "frame" || method == "settle") {
      capture_ = id;
      barrier_only_ = method == "settle";
      draining_ = true;
      frame_ = command->GetInt("frame");
      browser_->GetHost()->Invalidate(PET_VIEW);
      Pump();
      return;
    }
    if (method == "finish") {
      const bool complete = finish_ && finish_();
      auto result = CefDictionaryValue::Create();
      if (metric_) result->SetDouble("encoderFlushSeconds", metric_(3));
      Reply(id, result, complete ? "" : "encoder completion failed");
      return;
    }
    if (method == "close") { Close(); return; }
    const auto params = command->GetDictionary("params");
    evaluating_ = true;
    evaluate_id_ = id;
    const int protocol = ++devtools_sequence_;
    protocol_requests_[protocol] = id;
    if (!browser_->GetHost()->ExecuteDevToolsMethod(protocol, method, params)) {
      protocol_requests_.erase(protocol);
      evaluating_ = false;
      evaluate_id_ = 0;
      Reply(id, nullptr, "DevTools command submission failed");
      return;
    }
    Pump();
  }
  void Pump() {
    if (pumping_ || (!evaluating_ && capture_ == 0 && load_ == 0)) return;
    pumping_ = true;
    browser_->GetHost()->SendExternalBeginFrame();
    CefPostDelayedTask(TID_UI, base::BindOnce(&Renderer::Tick, CefRefPtr<Renderer>(this)), 1);
  }
  void Tick() {
    pumping_ = false;
    // Refresh requests can be coalesced by Viz while another capture is in
    // flight. Retry until the requested refresh arrives, including static pages.
    if (capture_) browser_->GetHost()->Invalidate(PET_VIEW);
    Pump();
  }
  void Refresh() { browser_->GetHost()->Invalidate(PET_VIEW); }
 private:
  int devtools_sequence_ = 0;
  std::map<int,int> protocol_requests_;
  using Begin = int (*)(const char*, const char*, int, int, int, int, int);
  using Submit = int (*)(void*, int);
  using Finish = int (*)();
  using Metric = double (*)(int);
  Begin begin_ = nullptr;
  Submit submit_ = nullptr;
  Finish finish_ = nullptr;
  Metric metric_ = nullptr;
  void* library_ = nullptr;
  CefRefPtr<CefBrowser> browser_;
  CefRefPtr<CefRegistration> registration_;
  int width_ = 640, height_ = 360, load_ = 0, capture_ = 0, frame_ = 0;
  int evaluate_id_ = 0;
  bool evaluating_ = false, pumping_ = false;
  bool draining_ = false;
  bool barrier_only_ = false;
  std::string load_url_;
  std::mutex resources_;
  std::string origin_ = "about:blank";
  std::vector<std::string> errors_;
  std::map<std::string, std::pair<double,int>> trace_;
  bool trace_complete_ = false;
  IMPLEMENT_REFCOUNTING(Renderer);
};

int main(int argc, char* argv[]) {
  CefScopedLibraryLoader loader;
  if (!loader.LoadInMain()) return 1;
  @autoreleasepool {
    [RendererApplication sharedApplication];
    [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];
    CefMainArgs args(argc, argv);
    CefSettings settings;
    settings.no_sandbox = true;
    settings.windowless_rendering_enabled = true;
    auto command = CefCommandLine::CreateCommandLine();
    command->InitFromArgv(argc, argv);
    CefString(&settings.root_cache_path) = command->GetSwitchValue("cache-path");
    CefRefPtr<Renderer> renderer = new Renderer;
    std::cerr << "VibeEdit initializing CEF" << std::endl;
    if (!CefInitialize(args, settings, renderer, nullptr)) return CefGetExitCode();
    std::cerr << "VibeEdit CEF initialized" << std::endl;
    CefRunMessageLoop();
    renderer = nullptr;
    CefShutdown();
  }
  return 0;
}
