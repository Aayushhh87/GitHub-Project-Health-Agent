import { Router, type IRouter } from "express";
import analysisRouter from "./analysis";
import healthRouter from "./health";

const router: IRouter = Router();

router.use(healthRouter);
router.use(analysisRouter);

export default router;
