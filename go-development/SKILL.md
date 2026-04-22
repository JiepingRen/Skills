---
name: go-development
description: Go 语言开发总则 - 编码规范、设计模式、项目结构最佳实践
metadata:
  hermes:
    tags: [Go, Golang, Backend, Design Patterns]
  lobehub:
    source: custom
---

# Go 开发总则

> 适用场景：Go 项目开发、代码审查、技术方案设计

## 一、核心理念

| 原则 | 说明 |
|------|------|
| **简单** | 少即是多，避免过度设计 |
| **可读** | 代码是给人读的 |
| **务实** | 解决实际问题 |
| **并发** | 优先用 channel 而非共享内存 |

---

## 二、模块索引

### 2.1 编码规范

📄 详细文档：[references/coding-standards.md](./references/coding-standards.md)

**快速要点**：

| 模块 | 核心规则 |
|------|----------|
| 命名 | 包名短小、驼峰命名、接口以 er 结尾 |
| 注释 | 导出函数必须有 godoc 注释 |
| 格式化 | gofmt 自动处理，import 分组 |
| 错误 | 始终处理，用 %w 包装 |

### 2.2 设计模式

📄 详细文档：[references/design-patterns.md](./references/design-patterns.md)

**常用模式**：

| 分类 | 模式 |
|------|------|
| 创建型 | 单例(包级变量)、工厂、建造者、Option模式 |
| 结构型 | 适配器、装饰器、代理、Composition |
| 行为型 | 策略、观察者、命令、责任链 |
| Go特色 | Functional Options, Pipe Pattern |

### 2.3 项目结构

📄 详细文档：[references/project-structure.md](./references/project-structure.md)

**标准布局**：

```
cmd/          → 应用入口
internal/    → 私有代码（不可导入）
pkg/         → 公开可复用
api/         → 协议定义
configs/     → 配置文件
```

---

## 三、编码规范速览

### 3.1 命名规范

```go
// 包名：简短、全小写
package model

// 函数/变量：驼峰
var userName string

// 接口：以 er 结尾
type Reader interface {}

// 类型：不加冗余后缀
type UserService  // ✅
type UserManager  // ❌
```

### 3.2 错误处理

```go
// ✅ 正确
func ReadFile(path string) ([]byte, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("读取文件 %s: %w", path, err)
    }
    return data, nil
}

// ❌ 忽略错误
data, _ := os.ReadFile(path)
```

---

## 四、检查清单

编码自检（开发时）：
- [ ] 包名是否简洁
- [ ] 导出是否有 godoc 注释
- [ ] 错误是否处理（不忽略）
- [ ] 是否用 defer 关闭资源
- [ ] 并发是否用 channel
- [ ] 是否通过 go vet

Code Review 检视：
- [ ] 命名是否符合规范
- [ ] 错误是否包含上下文
- [ ] 资源是否正确关闭
- [ ] 是否有 race condition

---

## 五、References（详细参考）

- [编码规范详解](./references/coding-standards.md)
- [设计模式实现](./references/design-patterns.md)
- [项目结构模板](./references/project-structure.md)

---

*文档版本：v2.0*
*更新日期：2026-04-22*