# Go 编码规范详解

> 参考：Go Code Review Comments、Effective Go、Google Go Style

## 一、命名规范

### 1.1 包名

```go
// ✅ 最佳实践
package model      // 简短、全小写
package user      // 与目录名一致
package httputil   // 多个词可拼接

// ❌ 避免
package Models    // 大写
package my_model // 下划线
package util    // 太笼统
```

### 1.2 导出/非导出

```go
// 导出：首字母大写，可被外部访问
var MaxConnections = 100
type User struct { ... }

// 非导出：首字母小写，仅限包内
var defaultConfig = Config{...}
type userService struct { ... }
```

### 1.3 函数名

```go
// ✅ 动词开头
func GetUser(id int) (*User, error)
func ValidateEmail(email string) bool
func NewUserService(repo UserRepo) *UserService

// ❌ 避免
func Get(id int)    // 省略号
func UserGet(id int) // 冗余前缀
```

### 1.4 变量名

```go
// ✅ 有意义，不冗余
var users map[int]*User
var pendingCount int

// ❌ 避免
var usrs map[int]*User    // 缩写不明确
var cnt int               // 单字母
var temp, temp1, temp2   // 无意义
```

### 1.5 常量

```go
// 状态类：驼峰
const StatusPending = "pending"
const StatusActive = "active"

// 全局配置：全大写
const MaxRetryCount = 3
const DefaultTimeout = 5 * time.Second
```

### 1.6 接口

```go
// ✅ 单方法接口以 er 结尾
type Reader interface {
    Read(p []byte) (n int, err error)
}

type Writer interface {
    Write(p []byte) (n int, err error)
}
```

### 1.7 类型名

```go
// ✅ 简洁
type Config struct{...}
type Handler func() error

// ❌ 避免
type Configuration struct{...}
type UserManagerService struct{...}
```

---

## 二、注释规范

### 2.1 导出函数注释

```go
// UserService 处理用户相关业务操作。
// 通过 NewUserService 创建实例。
type UserService struct{...}

// NewUserService 创建 UserService 实例。
// repo 用于数据持久化，timeout 控制操作超时。
func NewUserService(repo UserRepo, timeout time.Duration) *UserService
```

### 2.2 包注释

```go
// package model 定义核心数据模型。
//
// 类型说明：
//   - User: 用户实体
//   - Order: 订单实体
package model
```

### 2.3 注释风格

```go
// ✅ 简短，句号结尾
// ComputeHash calculates SHA-256 hash of data.

// ❌ 避免
// get retrieves the // 无意义重复
```

---

## 三、格式化

### 3.1 import 分组

```go
import (
    // 标准库
    "bytes"
    "context"
    "fmt"
    
    // 第三方
    "github.com/spf13/viper"
    "golang.org/x/sync/errgroup"
    
    // 项目内部
    "myproject/internal/model"
    "myproject/pkg/utils"
)
```

### 3.2 结构体字面量

```go
// ✅ 命名字段
user := User{
    Name:  "John",
    Age:   30,
    Email: "john@example.com",
}
```

---

## 四、错误处理

### 4.1 基本原则

```go
// ✅ 始终处理错误
func Read(path string) ([]byte, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }
    return data, nil
}

// ❌ 不要忽略错误
data, _ := os.ReadFile(path)
```

### 4.2 错误包装

```go
// ✅ 使用 %w 包装
func ReadFile(path string) ([]byte, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("读取文件 %s 失败: %w", path, err)
    }
    return data, nil
}

// 调用方可以 unwrap
if errors.Is(err, os.ErrNotExist) { ... }
```

### 4.3 sentinel errors

```go
var ErrNotFound = errors.New("not found")

func Find(id int) (*User, error) {
    if notFound {
        return nil, ErrNotFound
    }
    ...
}

if errors.Is(err, ErrNotFound) { ... }
```

---

## 五、并发安全

### 5.1 mutex

```go
type Counter struct {
    mu    sync.Mutex
    count int
}

func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}
```

### 5.2 channel

```go
// 生产者-消费者
func worker(ch chan<- int) {
    for i := 0; i < 10; i++ {
        ch <- i
    }
    close(ch)
}
```

### 5.3 sync.WaitGroup

```go
var wg sync.WaitGroup
for _, url := range urls {
    wg.Add(1)
    go func(url string) {
        defer wg.Done()
        fetch(url)
    }(url)
}
wg.Wait()
```

---

## 六、资源管理

### defer 关闭资源

```go
func Read(path string) ([]byte, error) {
    f, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer f.Close()
    
    return io.ReadAll(f)
}
```

---

## 七、检查清单

编码自检：
- [ ] 包名是否简洁
- [ ] 导出是否有 godoc 注释
- [ ] import 是否分组排序
- [ ] 错误是否处理（不忽略）
- [ ] 错误是否有上下文 (%w)
- [ ] 是否用 defer 关闭资源
- [ ] 并发是否安全
- [ ] 是否通过 go vet

---

*文档版本：v2.0*
*更新日期：2026-04-22*