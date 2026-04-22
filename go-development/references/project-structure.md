# Go 项目结构最佳实践

> 参考：Standard Go Project Layout

## 一、标准布局

### 1.1 完整项目结构

```
myproject/
├── cmd/                      # 可执行应用入口
│   ├── myapp/               # 单个应用
│   │   └── main.go
│   └── myapp2/              # 可多个应用
│       └── main.go
│
├── internal/                 # 私有代码（不可被外部导入）
│   ├── handler/             # HTTP/RPC 处理层
│   ├── service/            # 业务逻辑层
│   ├── repo/              # 数据访问层
│   ├── model/             # 数据模型
│   ├── middleware/        # 中间件
│   └── config/            # 配置加载
│
├── pkg/                     # 公开可复用代码
│   ├── utils/
│   └── validator/
│
├── api/                     # API 协议定义
│   ├── openapi.yaml
│   └── proto/
│       ├── user.proto
│       └── order.proto
│
├── configs/                 # 配置文件
│   ├── config.yaml
│   └── config-prod.yaml
│
│
├── scripts/                 # 脚本
│   ├── build.sh
│   └── migrate.sh
│
├── docs/                    # 文档
│
├── test/
│   └── e2e/               # E2E 测试
│
├── web/                     # 静态资源
│   ├── static/
│   └── templates/
│
├── go.mod                  # 模块定义
├── go.sum                  # 依赖锁定
└── Makefile               # 构建脚本
```

### 1.2 简化项目（小型服务）

```
myproject/
├── cmd/
│   └── server/
│       └── main.go
│
├── internal/
│   ├── config/
│   ├── handler/
│   ├── service/
│   ├── repo/
│   └── model/
│
├── go.mod
├── go.sum
└── Makefile
```

---

## 二、模块分层

### 2.1 分层架构

```
┌─────────────────────────────────────────┐
│          Handler Layer (HTTP/RPC)        │
└─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────┐
│            Service Layer                │
└─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────┐
│             Repo Layer                  │
└─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────┐
│            Data Layer (DB)             │
└─────────────────────────────────────────┘
```

### 2.2 模块交互

```go
// cmd/server/main.go
func main() {
    cfg := config.Load()
    
    repo := repo.NewMySQL(cfg.DSN)
    cache := repo.NewRedis(cfg.RedisAddr)
    svc := service.NewUserService(repo, cache)
    handler := handler.NewUserHandler(svc)
    
    http.ListenAndServe(":8080", handler)
}
```

---

## 三、go.mod 规范

### 3.1 模块定义

```makefile
module github.com/username/myproject

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/spf13/viper v1.17.0
)
```

### 3.2 依赖管理

```makefile
# 保持依赖清洁
go mod tidy

# 列出直接依赖
go list -m all

# 升级
go get github.com/gin-gonic/gin@v1.9.1
go get github.com/gin-gonic/gin@latest
```

---

## 四、Makefile 规范

### 4.1 标准 Makefile

```makefile
BINARY_NAME=myproject
GO=go
GOFLAGS=-v -race
LDFLAGS=-s -w

.PHONY: build clean test lint vet fmt run deps

build:
	$(GO) build -o bin/$(BINARY_NAME) -ldflags "$(LDFLAGS)" ./cmd/$(BINARY_NAME)

test:
	$(GO) test -v -race -cover ./...

lint:
	golint ./... && go vet ./...

fmt:
	gofumpt -w .

clean:
	rm -rf bin/

deps:
	go mod download
	go mod tidy
```

### 4.2 Docker 构建

```makefile
docker-build:
	docker build -t $(BINARY_NAME):latest .

docker-run:
	docker run -d -p 8080:8080 $(BINARY_NAME):latest
```

---

## 五、测试文件组织

### 5.1 测试命名

```
user.go              → 对应
user_test.go          → 单元测试
user_integration_test.go → 集成测试
```

### 5.2 目录结构

```
internal/
├── user.go
├── user_test.go
└── service/
    ├── service.go
    └── service_test.go

test/
└── e2e/
    └── main_test.go
```

---

## 六、检查清单

项目创建：
- [ ] 是否使用 go.mod 管理依赖
- [ ] cmd/ 目录是否包含所有可执行入口
- [ ] internal/ 是否正确分离
- [ ] 是否有 Makefile
- [ ] 是否有 .gitignore

代码组织：
- [ ] 分层是否清晰（Handler → Service → Repo）
- [ ] 是否有循环依赖
- [ ] 包名是否与目录名一致

---

*文档版本：v2.0*
*更新日期：2026-04-22*