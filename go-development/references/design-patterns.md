# Go 设计模式实现

> 参考：Design Patterns in Go - 适配 Go 语言特性的实现

## 一、设计原则

| Go 特性 | 传统 OOP | Go 实践 |
|--------|----------|---------|
| 无类 | 类 | struct + 方法 |
| 无继承 | 继承 | 组合 (Embedding) |
| 无多态 | 多态 | interface |
| 无构造函数 | 构造函数 | 工厂函数 + NewXXX |

---

## 二、创建型模式

### 2.1 单例模式

**包级变量（推荐）**：
```go
// 对于大多数场景，包级变量即单例
var defaultClient = &http.Client{
    Timeout: 30 * time.Second,
}

func GetClient() *http.Client {
    return defaultClient
}
```

**sync.Once**：
```go
var instance *singleton
var once sync.Once

func GetInstance() *singleton {
    once.Do(func() {
        instance = &singleton{data: "default"}
    })
    return instance
}
```

### 2.2 工厂模式

```go
type UserType int
const (
    TypeAdmin UserType = iota
    TypeGuest
    TypeRegular
)

func NewUser(t UserType) User {
    switch t {
    case TypeAdmin:
        return &AdminUser{User: User{Role: "admin"}}
    case TypeGuest:
        return &GuestUser{User: User{Role: "guest"}}
    default:
        return &RegularUser{User: User{Role: "regular"}}
    }
}
```

### 2.3 建造者模式

```go
type User struct {
    Name  string
    Email string
    Age   int
}

type UserBuilder struct {
    user User
}

func NewUserBuilder() *UserBuilder {
    return &UserBuilder{}
}

func (b *UserBuilder) Name(name string) *UserBuilder {
    b.user.Name = name
    return b
}

func (b *UserBuilder) Email(email string) *UserBuilder {
    b.user.Email = email
    return b
}

func (b *UserBuilder) Build() *User {
    return &b.user
}

// 使用
user := NewUserBuilder().
    Name("John").
    Email("john@example.com").
    Build()
```

---

## 三、结构型模式

### 3.1 适配器模式

```go
// 目标接口
type Player interface {
    Play(filename string)
}

// 现有实现
type LegacyPlayer struct{}
func (p *LegacyPlayer) PlayMusic(filename string) { ... }

// 适配器
type LegacyPlayerAdapter struct {
    *LegacyPlayer
}

func (a *LegacyPlayerAdapter) Play(filename string) {
    a.PlayMusic(filename)
}

// 使用
var player Player = &LegacyPlayerAdapter{&LegacyPlayer{}}
player.Play("song.mp3")
```

### 3.2 装饰器模式

```go
type Reader interface {
    Read(p []byte) (n int, err error)
}

// 缓冲读取装饰器
type BufferedReader struct {
    r   Reader
    buf []byte
}

func NewBufferedReader(r Reader, size int) *BufferedReader {
    return &BufferedReader{r: r, buf: make([]byte, size)}
}

func (b *BufferedReader) Read(p []byte) (n int, err error) {
    // 缓冲逻辑
}
```

### 3.3 代理模式

```go
type Service interface {
    DoSomething()
}

type RealService struct{}
func (s *RealService) DoSomething() { ... }

// 代理
type ServiceProxy struct {
    svc Service
}

func (p *ServiceProxy) DoSomething() {
    // 前置处理
    p.svc.DoSomething()
    // 后置处理
}
```

### 3.4 组合 (Embedding)

```go
type Logger struct {
    Prefix string
}

func (l *Logger) Log(msg string) {
    fmt.Printf("[%s] %s\n", l.Prefix, msg)
}

type UserService struct {
    Logger  // 组合
    repo    UserRepo
}

func (s *UserService) Create(u User) error {
    s.Log("creating user: " + u.Name)
    return s.repo.Save(u)
}
```

---

## 四、行为型模式

### 4.1 策略模式

```go
type SortStrategy interface {
    Sort([]int) []int
}

type QuickSort struct{}
func (s *QuickSort) Sort(arr []int) []int { ... }

type BubbleSort struct{}
func (s *BubbleSort) Sort(arr []int) []int { ... }

type Sorter struct {
    strategy SortStrategy
}

func (s *Sorter) SetStrategy(strategy SortStrategy) {
    s.strategy = strategy
}

func (s *Sorter) Sort(arr []int) []int {
    return s.strategy.Sort(arr)
}
```

### 4.2 观察者模式

```go
type Event struct {
    Type    string
    Payload interface{}
}

type Observer interface {
    OnEvent(Event)
}

type Publisher struct {
    observers []Observer
}

func (p *Publisher) Subscribe(obs Observer) {
    p.observers = append(p.observers, obs)
}

func (p *Publisher) Publish(event Event) {
    for _, obs := range p.observers {
        obs.OnEvent(event)
    }
}
```

### 4.3 命令模式

```go
type Command interface {
    Execute()
    Undo()
}

type CommandFunc struct {
    do, undo func()
}

func (c *CommandFunc) Execute() { c.do() }
func (c *CommandFunc) Undo() { c.undo() }

type Invoker struct {
    commands []Command
}

func (i *Invoker) Execute(cmd Command) {
    cmd.Execute()
    i.commands = append(i.commands, cmd)
}
```

### 4.4 责任链

```go
type Handler interface {
    SetNext(Handler)
    Handle(Request) error
}

type Middleware struct {
    next Handler
}

func (m *Middleware) SetNext(next Handler) { m.next = next }

func (m *Middleware) Handle(req Request) error {
    // 处理
    if m.next != nil {
        return m.next.Handle(req)
    }
    return nil
}
```

---

## 五、Go 特有模式

### 5.1 Option 模式

```go
type Options struct {
    Timeout time.Duration
    Retry   int
    Debug   bool
}

type Option func(*Options)

func WithTimeout(t time.Duration) Option {
    return func(o *Options) { o.Timeout = t }
}

func WithDebug(d bool) Option {
    return func(o *Options) { o.Debug = d }
}

func NewClient(opts ...Option) *Client {
    opt := &Options{Timeout: 30 * time.Second, Retry: 3}
    for _, o := range opts { o(opt) }
    return &Client{timeout: opt.Timeout}
}

// 使用
client := NewClient(WithTimeout(60*time.Second), WithDebug(true))
```

### 5.2 Functional Options

```go
type Server struct {
    Addr     string
    Port     int
    Timeout  time.Duration
}

type ServerOption func(*Server)

func Addr(addr string) ServerOption {
    return func(s *Server) { s.Addr = addr }
}

func Port(port int) ServerOption {
    return func(s *Server) { s.Port = port }
}

func NewServer(opts ...ServerOption) *Server {
    s := &Server{Addr: "localhost", Port: 8080}
    for _, opt := range opts { opt(s) }
    return s
}
```

### 5.3 Pipe Pattern

```go
type Pipe func([]int) []int

func Filter(fn func(int) bool) Pipe {
    return func(data []int) []int {
        result := make([]int, 0)
        for _, v := range data {
            if fn(v) { result = append(result, v) }
        }
        return result
    }
}

func Map(fn func(int) int) Pipe {
    return func(data []int) []int {
        result := make([]int, len(data))
        for i, v := range data { result[i] = fn(v) }
        return result
    }
}

func Pipeline(data []int, pipes ...Pipe) []int {
    result := data
    for _, pipe := range pipes { result = pipe(result) }
    return result
}

// 使用
result := Pipeline(
    []int{1, 2, 3, 4, 5},
    Filter(func(x int) bool { return x > 2 }),
    Map(func(x int) int { return x * 2 }),
)
```

---

## 六、检查清单

模式选择：
- [ ] 是否真的需要模式（避免过度设计）
- [ ] Go 特性是否已满足需求
- [ ] 组合是否优于继承
- [ ] 是否有资源泄露

---

*文档版本：v2.0*
*更新日期：2026-04-22*